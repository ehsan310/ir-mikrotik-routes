#!/usr/bin/env python3
"""Find and re-check IPv4 ranges that are used in Iran but that ipverse lists
under another country. Keeps custom_ips.txt up to date (see AGENTS.md).

  scan      Add ranges from the ipverse lists of the countries in
            scan_countries.txt that pass the Iran check.
  validate  Re-check every custom_ips.txt entry and remove (or carve out)
            the parts that fail it.

Iran check, per address:
  1. RIPE Database: the most specific inetnum covering it has country IR.
  2. Routing (RIPE RIS, announcements seen by at least MIN_PEERS peers): the
     most specific announcement covering it is originated by an AS registered
     in IR, or by an AS whose upstream neighbours (RIPEstat) are all in IR.
  "scan" needs both. "validate" removes parts that fail 1, or that are
  announced and fail 2; unannounced parts are kept so a short outage does not
  drop them.
"""
import argparse
import bisect
import gzip
import ipaddress
import json
import os
import shutil
import socket
import struct
import sys
import time
import urllib.error
import urllib.request

RIPE_INETNUM = "https://ftp.ripe.net/ripe/dbase/split/ripe.db.inetnum.gz"
RIS_DUMP = "https://www.ris.ripe.net/dumps/riswhoisdump.IPv4.gz"
NRO_STATS = "https://ftp.ripe.net/pub/stats/ripencc/nro-stats/latest/nro-delegated-stats"
IPVERSE = "https://raw.githubusercontent.com/ipverse/rir-ip/master/country/{cc}/ipv4-aggregated.txt"
RIPESTAT_NEIGHBOURS = "https://stat.ripe.net/data/asn-neighbours/data.json?resource=AS{asn}&sourceapp=ir-mikrotik-routes"
USER_AGENT = "ir-mikrotik-routes (+https://github.com/ehsan310/ir-mikrotik-routes)"
MIN_PEERS = 10          # ignore announcements seen by fewer RIS peers (leaks, noise)
MAX_AGE = 20 * 3600     # reuse downloaded files younger than this
REMOVAL_LIMIT = 0.25    # validate refuses to remove more than this share of addresses at once


class DataError(Exception):
    """Source data could not be downloaded or looks broken."""


# --------------------------------------------------------------------------- helpers
def ip2int(text):
    return struct.unpack("!I", socket.inet_aton(text.strip()))[0]


def cidrs(start, end):
    return list(ipaddress.summarize_address_range(ipaddress.IPv4Address(start), ipaddress.IPv4Address(end)))


def span(net):
    return int(net.network_address), int(net.broadcast_address)


def merge(ivs):
    out = []
    for s, e in sorted(ivs):
        if out and s <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def subtract(ivs, minus):
    """Parts of the (merged) intervals `ivs` not covered by the (merged) intervals `minus`."""
    out, j = [], 0
    for s, e in ivs:
        cur = s
        while j < len(minus) and minus[j][1] < cur:
            j += 1
        k = j
        while k < len(minus) and minus[k][0] <= e:
            if minus[k][0] > cur:
                out.append((cur, minus[k][0] - 1))
            cur = max(cur, minus[k][1] + 1)
            k += 1
        if cur <= e:
            out.append((cur, e))
    return out


def intersect(a, b):
    return subtract(a, subtract(a, b))


class Intervals:
    def __init__(self, ivs):
        self.iv = merge(ivs)
        self.starts = [s for s, _ in self.iv]

    def overlaps(self, s, e):
        i = bisect.bisect_right(self.starts, e) - 1
        return i >= 0 and self.iv[i][1] >= s


def paint(targets, items):
    """Split `targets` into segments owned by the most specific item covering them.

    items: (start, end, value), nested like prefixes/inetnums. Returns
    [(start, end, value or None)] covering exactly the target intervals."""
    bounds = {b for s, e in targets.iv for b in (s, e + 1)}
    bounds.update(b for s, e, _ in items for b in (s, e + 1))
    edges = sorted(bounds)
    owner = [None] * (len(edges) - 1)
    for s, e, value in sorted(items, key=lambda it: it[1] - it[0], reverse=True):
        for i in range(bisect.bisect_left(edges, s), bisect.bisect_left(edges, e + 1)):
            owner[i] = value
    out = []
    for i in range(len(edges) - 1):
        s, e = edges[i], edges[i + 1] - 1
        if not targets.overlaps(s, s):
            continue
        if out and out[-1][2] is owner[i] and out[-1][1] + 1 == s:
            out[-1] = (out[-1][0], e, owner[i])
        else:
            out.append((s, e, owner[i]))
    return out


def fetch(url, path, max_age=MAX_AGE):
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age:
        return path
    error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response, open(path + ".part", "wb") as out:
                shutil.copyfileobj(response, out, 1 << 20)
            os.replace(path + ".part", path)
            return path
        except urllib.error.HTTPError as e:
            error = e
            if e.code == 404:
                break
        except OSError as e:
            error = e
        time.sleep(5 * (attempt + 1))
    raise DataError(f"could not download {url}: {error}")


# --------------------------------------------------------------------------- data
class Data:
    def __init__(self, data_dir):
        self.dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.inetnums = []
        self._asn_iv = None
        self._upstreams = {}

    def _file(self, name, url):
        return fetch(url, os.path.join(self.dir, name))

    def ipverse(self, cc):
        nets = []
        with open(self._file(f"ipverse-{cc}.txt", IPVERSE.format(cc=cc))) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    nets.append(ipaddress.IPv4Network(line, strict=False))
        return nets

    def load_inetnums(self, targets):
        """RIPE inetnum objects overlapping `targets`, as (start, end, {cc, netname})."""
        path = self._file("ripe.db.inetnum.gz", RIPE_INETNUM)
        items, cur, total = [], None, 0
        try:
            with gzip.open(path, "rt", encoding="latin-1") as f:
                for line in f:
                    if line.startswith("inetnum:"):
                        total += 1
                        if cur:
                            items.append(cur)
                        cur = None
                        value = line[8:].strip()
                        try:
                            if "-" in value:
                                a, b = value.split("-", 1)
                                s, e = ip2int(a), ip2int(b)
                            else:
                                s, e = span(ipaddress.IPv4Network(value, strict=False))
                        except (OSError, ValueError):
                            continue
                        if targets.overlaps(s, e):
                            cur = (s, e, {"cc": set(), "netname": ""})
                    elif cur:
                        if line.startswith("country:"):
                            cur[2]["cc"].add(line[8:].split("#")[0].strip().upper())
                        elif line.startswith("netname:"):
                            cur[2]["netname"] = line[8:].strip()
        except (OSError, EOFError) as e:
            raise DataError(f"broken RIPE inetnum dump: {e}")
        if cur:
            items.append(cur)
        if total < 1_000_000:
            raise DataError(f"RIPE inetnum dump looks truncated ({total} objects)")
        self.inetnums = items
        return items

    def load_announcements(self, targets):
        """RIS announcements overlapping `targets`, as (start, end, frozenset(origin ASNs))."""
        path = self._file("riswhoisdump.IPv4.gz", RIS_DUMP)
        items, total = {}, 0
        try:
            with gzip.open(path, "rt", encoding="latin-1") as f:
                for line in f:
                    if line.startswith("%") or not line.strip():
                        continue
                    total += 1
                    origin, prefix, peers = line.split("\t")
                    if int(peers) < MIN_PEERS:
                        continue
                    s, e = span(ipaddress.IPv4Network(prefix, strict=False))
                    if targets.overlaps(s, e):
                        asns = {int(a) for a in origin.strip("{}").split(",") if a.strip().isdigit()}
                        items.setdefault((s, e), set()).update(asns)
        except (OSError, EOFError, ValueError) as e:
            raise DataError(f"broken RIS dump: {e}")
        if total < 500_000:
            raise DataError(f"RIS dump looks truncated ({total} announcements)")
        return [(s, e, frozenset(asns)) for (s, e), asns in items.items()]

    def asn_country(self, asn):
        if self._asn_iv is None:
            ivs = []
            with open(self._file("nro-delegated-stats", NRO_STATS)) as f:
                for line in f:
                    p = line.split("|")
                    if len(p) > 6 and p[2] == "asn" and p[1] not in ("*", "") and p[3].isdigit():
                        ivs.append((int(p[3]), int(p[3]) + int(p[4]) - 1, p[1]))
            if len(ivs) < 50_000:
                raise DataError(f"NRO delegated stats look truncated ({len(ivs)} ASN records)")
            ivs.sort()
            self._asn_iv = (ivs, [s for s, _, _ in ivs])
        ivs, starts = self._asn_iv
        i = bisect.bisect_right(starts, asn) - 1
        return ivs[i][2] if i >= 0 and ivs[i][1] >= asn else "??"

    def upstreams_in_iran(self, asn):
        """True if the AS has upstream neighbours and they are all registered in IR."""
        if asn not in self._upstreams:
            url = RIPESTAT_NEIGHBOURS.format(asn=asn)
            for attempt in range(3):
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(request, timeout=60) as response:
                        neighbours = json.load(response)["data"]["neighbours"]
                    break
                except (OSError, ValueError, KeyError) as e:
                    error = e
                    time.sleep(5 * (attempt + 1))
            else:
                raise DataError(f"RIPEstat neighbours for AS{asn} failed: {error}")
            ups = {n["asn"] for n in neighbours if n.get("type") == "left"}
            self._upstreams[asn] = bool(ups) and all(self.asn_country(u) == "IR" for u in ups)
        return self._upstreams[asn]


def classify(targets, data):
    """[(start, end, status, reason)] over `targets`; status: iran, unannounced, abroad, not-ir."""
    out, ir_ivs = [], []
    for s, e, obj in paint(targets, data.load_inetnums(targets)):
        countries = obj["cc"] if obj else set()
        if countries == {"IR"}:
            ir_ivs.append((s, e))
        else:
            where = "/".join(sorted(countries)) or "none"
            out.append((s, e, "not-ir", f"RIPE country {where}"))
    ir = Intervals(ir_ivs)
    for s, e, origins in paint(ir, data.load_announcements(ir)):
        if not origins:
            out.append((s, e, "unannounced", "not announced"))
        elif any(data.asn_country(a) == "IR" for a in origins) or any(data.upstreams_in_iran(a) for a in origins):
            out.append((s, e, "iran", ""))
        else:
            names = ", ".join(f"AS{a} ({data.asn_country(a)})" for a in sorted(origins))
            out.append((s, e, "abroad", f"announced by {names}"))
    return sorted(out)


# --------------------------------------------------------------------------- files
def read_entries(path):
    """Lines of the file plus {line index: (network, comment)} for valid entry lines."""
    with open(path) as f:
        lines = f.read().splitlines()
    entries = {}
    for i, raw in enumerate(lines):
        body, _, comment = raw.partition("#")
        if not body.strip():
            continue
        try:
            entries[i] = (ipaddress.IPv4Network(body.strip()), comment.strip())
        except ValueError:
            pass  # left as-is; the build workflow reports invalid lines
    return lines, entries


def entry_line(net, comment):
    return f"{str(net):<18} # {comment}" if comment else str(net)


def write_lines(path, lines):
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_report(path, title, items):
    print(title)
    for item in items:
        print(f"::notice::{item}")
    if path:
        with open(path, "w") as f:
            f.write(title + "\n\n" + "\n".join(f"- {item}" for item in items) + "\n")


def describe(segments, limit=8):
    """Merge adjacent segments with the same reason into 'CIDR, CIDR (reason)' strings."""
    groups = []
    for s, e, _, why in segments:
        if groups and groups[-1][2] == why and groups[-1][1] + 1 == s:
            groups[-1][1] = e
        else:
            groups.append([s, e, why])
    text = [f"{', '.join(map(str, cidrs(s, e)[:4]))}{', ...' if len(cidrs(s, e)) > 4 else ''} ({why})"
            for s, e, why in groups[:limit]]
    return "; ".join(text) + (f"; and {len(groups) - limit} more" if len(groups) > limit else "")


# --------------------------------------------------------------------------- commands
def cmd_validate(args):
    lines, entries = read_entries(args.custom)
    if not entries:
        print("No custom entries to validate.")
        return 0
    targets = Intervals([span(net) for net, _ in entries.values()])
    try:
        segments = classify(targets, Data(args.data_dir))
    except DataError as e:
        print(f"::warning::Custom IP validation skipped: {e}")
        return 0
    bad = [seg for seg in segments if seg[2] in ("not-ir", "abroad")]
    if not bad:
        print(f"All {len(entries)} custom entries passed the Iran check.")
        return 0
    total = sum(e - s + 1 for s, e in targets.iv)
    removed = sum(e - s + 1 for s, e, _, _ in bad)
    if removed > REMOVAL_LIMIT * total and not args.force:
        print(f"::warning::Validation would remove {removed:,} of {total:,} custom addresses "
              f"(more than {REMOVAL_LIMIT:.0%}); nothing changed. Check the sources or run with --force. "
              f"Failing parts: {describe(bad)[:1500]}")
        return 0
    bad_iv = merge((s, e) for s, e, _, _ in bad)
    new_lines, report = [], []
    for i, raw in enumerate(lines):
        if i not in entries:
            new_lines.append(raw)
            continue
        net, comment = entries[i]
        keep = subtract([span(net)], bad_iv)
        if keep == [span(net)]:
            new_lines.append(raw)
            continue
        kept = [c for s, e in keep for c in cidrs(s, e)]
        new_lines.extend(entry_line(c, comment) for c in kept)
        s0, e0 = span(net)
        failed = [(max(s, s0), min(e, e0), st, why) for s, e, st, why in bad if s <= e0 and e >= s0]
        report.append(f"{net}: removed {describe(failed)}" + (f"; kept {', '.join(map(str, kept))}" if kept else ""))
    write_lines(args.custom, new_lines)
    write_report(args.report, f"Removed {removed:,} addresses that no longer pass the Iran check:", report)
    return 0


def cmd_scan(args):
    countries = []
    with open(args.countries) as f:
        for raw in f:
            cc = raw.split("#", 1)[0].strip().lower()
            if cc and cc != "ir":
                countries.append(cc)
    lines, entries = read_entries(args.custom)
    data = Data(args.data_dir)
    lists, sizes = {}, {}
    for cc in countries:
        try:
            nets = data.ipverse(cc)
            lists[cc], sizes[cc] = Intervals([span(n) for n in nets]), len(nets)
        except DataError as e:
            print(f"::warning::Skipping country '{cc}': {e}")
    if not lists:
        raise DataError("no country list could be downloaded")
    targets = Intervals([iv for ivs in lists.values() for iv in ivs.iv])
    segments = classify(targets, data)
    iran = merge((s, e) for s, e, st, _ in segments if st == "iran")
    new = subtract(iran, merge(span(net) for net, _ in entries.values()))
    ir_objs = [(s, e, o["netname"]) for s, e, o in data.inetnums if o["cc"] == {"IR"}]

    def label(cc, net):
        s, e = span(net)
        covering = [o for o in ir_objs if o[0] <= s and o[1] >= e]
        if covering:
            return f"{cc.upper()}: {max(covering, key=lambda o: o[1] - o[0])[2]}"
        names = list(dict.fromkeys(o[2] for o in sorted(ir_objs, key=lambda o: o[0] - o[1]) if o[0] <= e and o[1] >= s))
        return f"{cc.upper()}: {', '.join(names[:2])}" + (", ..." if len(names) > 2 else "")

    additions = []
    for cc, ivs in lists.items():
        found = sum(e - s + 1 for s, e in intersect(iran, ivs.iv))
        added = intersect(new, ivs.iv)
        print(f"{cc.upper()}: {sizes[cc]} ranges; {found:,} addresses pass the Iran check; "
              f"{sum(e - s + 1 for s, e in added):,} not yet in {args.custom}")
        additions += [(net, label(cc, net)) for s, e in added for net in cidrs(s, e)]
    if not additions:
        print("No new ranges.")
        return 0
    additions.sort(key=lambda a: a[0])
    new_lines, pending = [], list(additions)
    for i, raw in enumerate(lines):
        if i in entries:
            while pending and pending[0][0] < entries[i][0]:
                new_lines.append(entry_line(*pending.pop(0)))
        new_lines.append(raw)
    new_lines.extend(entry_line(*a) for a in pending)
    write_lines(args.custom, new_lines)
    total = sum(net.num_addresses for net, _ in additions)
    write_report(args.report, f"Added {len(additions)} ranges ({total:,} addresses) used in Iran:",
                 [f"{net} ({comment})" for net, comment in additions])
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=os.environ.get("IR_DATA_DIR", os.path.expanduser("~/.cache/ir-mikrotik-routes")),
                        help="where downloaded source data is kept (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="re-check custom_ips.txt entries")
    v.add_argument("--custom", default="custom_ips.txt")
    v.add_argument("--report", help="write a summary of removals to this file")
    v.add_argument("--force", action="store_true", help=f"allow removing more than {REMOVAL_LIMIT:.0%} at once")
    s = sub.add_parser("scan", help="add ranges from the countries in scan_countries.txt")
    s.add_argument("--countries", default="scan_countries.txt")
    s.add_argument("--custom", default="custom_ips.txt")
    s.add_argument("--report", help="write a summary of additions to this file")
    args = parser.parse_args()
    try:
        return cmd_validate(args) if args.command == "validate" else cmd_scan(args)
    except DataError as e:
        print(f"::error::{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

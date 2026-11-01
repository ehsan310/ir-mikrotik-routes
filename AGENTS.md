# Repository Guide

## Purpose

This repository generates MikroTik RouterOS scripts containing Iranian IPv4 ranges from ipverse's Iran list and `custom_ips.txt`. The custom list includes ranges used in Iran that ipverse attributes to another country because ipverse follows RIR allocation-holder data. Automation scans configured countries for candidates and validates custom ranges against RIPE data.

| File | Purpose |
| --- | --- |
| `iran_list.rsc` | Generated MikroTik firewall address-list script. |
| `iran_routes.rsc` | Generated MikroTik routing script. |
| `custom_ips.txt` | Custom IPv4 ranges, both manually maintained and automatically scanned. |
| `scan_countries.txt` | Country codes whose ipverse lists are scanned for Iranian ranges. |
| `scripts/ir_ranges.py` | Python tool for scanning candidate ranges and validating custom ranges. |
| `.github/workflows/update-iran-ips.yml` | Validates custom ranges and generates the MikroTik scripts. |
| `.github/workflows/scan-countries.yml` | Scans configured countries and adds qualifying ranges. |
| `README.md` | User-facing project overview and usage instructions. |

## Workflows

### Generate MikroTik Iran IP List

`.github/workflows/update-iran-ips.yml` runs daily at 02:00 UTC, on manual dispatch, and when `custom_ips.txt` changes on `main`. It validates `custom_ips.txt`, merges it with ipverse's Iran list (deduplicating and collapsing ranges; malformed lines fail the run), and generates the `.rsc` scripts. It commits only if `custom_ips.txt` or generated IP data changed; timestamp-only changes are ignored. The bot uses commit message `chore(data): update Iran IP list`, puts removal reasons in the commit body, and retries a push after rebasing.

### Scan Countries for Iranian IP Ranges

`.github/workflows/scan-countries.yml` runs weekly on Monday at 03:00 UTC, on manual dispatch, and when `scan_countries.txt` changes on `main`. It runs `scan`; if ranges are added, it commits them with `chore(data): add scanned Iranian IP ranges` and lists the ranges in the commit body. It then starts the build workflow with `gh workflow run`, because pushes made using `GITHUB_TOKEN` do not trigger workflows.

## The Iran check

The check evaluates each IPv4 address using both registry and routing data:

1. **RIPE Database:** the most-specific `inetnum` covering the address must have country `IR` (only `IR` qualifies).
2. **Routing:** the most-specific BGP announcement covering the address, from a RIPE RIS dump and seen by at least 10 RIS peers, must be originated either by an AS registered in `IR` according to NRO delegated statistics, or by an AS whose RIPEstat `asn-neighbours` `left` upstream neighbours are all registered in `IR`.

`scan` adds only addresses passing both checks. `validate` removes custom addresses that fail the RIPE country check or that are announced but fail the routing check. Unannounced addresses are kept so a short outage does not remove them. If a custom CIDR only partly fails, validation cuts out the failing portion and retains the remaining CIDRs with the original comment.

Safety measures:

- If a source cannot be downloaded or appears truncated, `validate` warns and makes no changes, allowing the build to continue. `scan` fails instead.
- Truncation thresholds are fewer than 1 million RIPE `inetnum` records, fewer than 500,000 RIS announcements, or fewer than 50,000 NRO ASN records.
- `validate` refuses to remove more than 25% of custom addresses in one run unless `--force` is supplied; it warns when it refuses.

## Data sources

- **ipverse country lists:** `https://raw.githubusercontent.com/ipverse/rir-ip/master/country/<cc>/ipv4-aggregated.txt` (including `ir` and the configured scan countries).
- **RIPE Database split dump:** `https://ftp.ripe.net/ripe/dbase/split/ripe.db.inetnum.gz` (about 224 MB, updated daily).
- **RIPE RIS IPv4 dump:** `https://www.ris.ripe.net/dumps/riswhoisdump.IPv4.gz`.
- **NRO delegated statistics:** `https://ftp.ripe.net/pub/stats/ripencc/nro-stats/latest/nro-delegated-stats`.
- **RIPEstat ASN neighbours API:** `asn-neighbours`, queried only for the few non-IR origin ASes that need upstream checking.

All sources except ipverse are from RIPE NCC.

## Running locally

Run these commands from the repository root with Python 3 (the tool uses only the standard library):

```sh
python3 scripts/ir_ranges.py validate
python3 scripts/ir_ranges.py scan
```

The first run downloads about 290 MB of source data into `~/.cache/ir-mikrotik-routes`. Use `--data-dir PATH` to select another directory, or set `IR_DATA_DIR`; downloads younger than 20 hours are reused. `validate` also accepts `--report FILE` and `--force`; `scan` accepts `--report FILE`.

## Scan notes

### 2026-11-01 — United Arab Emirates (AE)

ipverse lists these ranges under AE (UAE IP brokers such as IPMASTER, ALNAFETHA, and AIROSERVER), but the most-specific RIPE `inetnum` says country `IR` and the ranges are announced from Iran: by IR-registered ASNs or by AS39368 (registered in AE, with all upstreams Iranian). Sources: ipverse country/ae, RIPE DB `inetnum` dump 2026-10-31, and CAIDA RouteViews prefix2as 2026-10-31 (the automated check now uses RIPE RIS instead of CAIDA).

Result: 40 ranges and 157,440 addresses, plus the earlier manual entry `77.104.64.0/18` (`AE-IPMASTER-20081007`, Respina AS42337). Of the AE list (1,223 prefixes, 7.27 million addresses), only 2.4% has RIPE country `IR`.

Left out despite RIPE country `IR`, because announced or geolocated outside Iran:

- `5.160.111.0/24` — AS60539, HK; geolocated Frankfurt.
- `31.56.54.0/24` — unannounced; geolocated AE.
- `31.59.169.0/24` — unannounced; geolocated TR.
- `94.183.172.0/24` — AS210814, GB; mostly non-Iranian upstreams.
- `94.183.192.0/24` and `94.183.216.0/24` — AS58232, AU; geolocated AE.

### 2026-11-01 — Oman (OM), Azerbaijan (AZ), Armenia (AM) preview

Automated-check results: OM, none; AZ, `5.10.248.0/24` (Potenting, AS212607 IR); AM, `185.255.68.0/23` and `185.255.70.0/24` (`AM-REGIKA-20180413`).

The AM ranges are a judgement call: their origin AS203739 is registered in AM and MaxMind geolocates them to AM, but RIPE says `IR` and the AS's only upstream is AS48147 (IR), so traffic reaches it through Iran; they were kept.

## Conventions

- Use Conventional Commits for every commit: `<type>(<scope>): <description>`.
- Do not hand-edit generated `.rsc` files.
- Keep `custom_ips.txt` to ranges and short comments; put explanations in this file.
- Manual entries in `custom_ips.txt` are subject to the same automatic validation as scanned entries.

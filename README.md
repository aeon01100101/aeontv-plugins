# AeonTV Plugins — Jellyfin Plugin Repository

Custom plugins for **AeonTV / Jellyfin** (Linux), by Isaiah. Builds for both **10.10.x** and **12.x** are in the manifest — your server automatically gets the one matching its version.

## Add this repository in Jellyfin

1. Dashboard → **Plugins** → **Repositories** → **＋ Add**
2. Name: `AeonTV Plugins`
3. URL:

   ```
   https://raw.githubusercontent.com/aeon01100101/aeontv-plugins/main/manifest.json
   ```

4. Save. The plugins below appear in the plugin **Catalog** — install
   and update them right from Jellyfin. Restart the server after
   installing, like any plugin.

## Plugins

| Plugin | What it does |
| --- | --- |
| **Bandwidth Tracker** 1.1.0.0 | Records every login and how much bandwidth each user/profile streams, with a dashboard page. |
| **Aeon Profiles** 1.2.0.0 | Netflix-style accounts + profiles: one account, several profiles, PINs, kids rating caps, and per-title blocks. |
| **Aeon Home** 1.1.0.0 | A "For You" home: Top Picks per profile, Because You Watched, server Top 10, thumbs ratings, hide-from-history. |
| **Aeon Identify** 1.1.0.0 | An inbox of files that look mislabeled or unidentified — it asks you what each one really is, applies Jellyfin's Identify, and can rename the file to match. |
| **AeonPS1** 1.1.0.0 | A PlayStation games shelf inside AeonTV: real serial/region detection from disc bytes, disc streaming, Play hand-off to the AeonPS1 app. |

## Requirements

- Jellyfin / AeonTV on Linux: **10.10.x** (`targetAbi 10.10.7.0`, .NET 8) or **12.x** (`targetAbi 12.2.0.0`, .NET 10).
- The manifest carries both builds of every plugin; Jellyfin installs the one that matches your server.

The plugin zips are attached to this repo's
[Releases](https://github.com/aeon01100101/aeontv-plugins/releases);
`manifest.json` points at them with MD5 checksums, the way Jellyfin's
repository system expects.

---
description: Build-in-Public — generate posts from your engineering work, anonymize, and schedule via Buffer
---

# Build-in-Public Commands

## Enable for this project

To enable the build-in-public plugin for the current project:

```
/build-in-public enable
```

This activates post generation for significant work events: PR merged, feature shipped, review passed.

## Manage brands

By default, ALL company names are anonymized. To explicitly allow a brand:

```
/build-in-public add brand Protagé
/build-in-public add brand edubites
```

Brands added this way appear by name in posts. Everything else stays anonymized.

## Manage clickouts

To add a URL that gets appended to posts (especially X/Twitter):

```
/build-in-public add clickouts to https://github.com/alinaqi/maggy
/build-in-public add clickouts to https://edubites.ai
```

Multiple URLs are supported. X posts always include the first clickout.

## Customization file

Your guidelines are stored in the plugin's `customization.md` file. When you change a setting via slash command, it updates this file:

```
~/.maggy/plugins/build-in-public/customization.md
```

The plugin reads this file on every post generation — no restart needed.

## Disable

```
/build-in-public disable
```

Pauses post generation for the current project.

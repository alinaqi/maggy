Set the issue tracker for the current project.

Usage:
```
/set-tracker native     # Use _project_specs/todos/ (default)
/set-tracker github     # Use GitHub Issues
/set-tracker asana      # Use Asana
/set-tracker monday     # Use Monday.com
```

This updates the per-project config. Subsequent `/inbox` or task operations use the selected tracker.

To check current tracker:
```
/set-tracker status
```

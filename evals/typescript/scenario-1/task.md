# Task: Build a Task Queue Library

Create a TypeScript task queue that:
- Accepts async functions with priority levels
- Processes tasks with configurable concurrency
- Supports retry with exponential backoff
- Emits events: task:start, task:complete, task:fail

Export types and the main class from an index.ts barrel file.

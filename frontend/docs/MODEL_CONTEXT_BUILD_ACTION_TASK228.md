# Task 228 — Model context build action

Task 228 closes a UX gap in the Models tab.

Before this task, the workspace could show a selected AI model and a selected
search model, but the user still had to know that the next required step was to
build searchable context. This was easy to confuse with an embedding model setup
problem.

The Models screen now presents the next action directly when the search model is
selected but the workspace context has not been indexed yet:

1. confirm selected AI/search models;
2. build context with the selected search model;
3. wait for the backend workspace job status;
4. refresh the model dashboard after completion;
5. use Ask with local sources.

Safety boundaries remain unchanged:

- the frontend does not execute shell commands;
- context build starts only after an explicit user click;
- model downloads remain backend-side approved jobs;
- changing the selected embedding model still does not rebuild the index automatically.

## Hi there 👋

<!--
**rosemary-memory/rosemary-memory** is a ✨ _special_ ✨ repository because its `README.md` (this file) appears on your GitHub profile.

Here are some ideas to get you started:

<<<<<<< HEAD
- 🔭 I’m currently working on ...
- 🌱 I’m currently learning ...
- 👯 I’m looking to collaborate on ...
- 🤔 I’m looking for help with ...
- 💬 Ask me about ...
- 📫 How to reach me: ...
- 😄 Pronouns: ...
- ⚡ Fun fact: ...
-->
=======
### Environment
- `OPENAI_API_KEY` (required)
- `OPENAI_MODEL` (default: `gpt-4o-mini`)
- `OPENAI_BASE_URL` (optional)
- `DATABASE_URL` (required)
- `AGE_GRAPH_NAME` (default: `gmemory`)

Example `DATABASE_URL` for the docker compose setup:
- `postgresql+asyncpg://rosemary:rosemary@localhost:5455/rosemary`

### Run
```
rosemary-memory run --prompt "Remember that my favorite theme is warm minimalism"
rosemary-memory store --text "My favorite theme is warm minimalism"
rosemary-memory retrieve --query "favorite theme"
rosemary-memory export-graph
rosemary-memory export-graph --format png
rosemary-memory export-graph --format svg
```

### What it does
- Clusters details into coarse topics (LLM-based)
- Stores `Cluster → Summary → Detail` nodes in AGE
- Retrieves memory and feeds it into the agent loop

### Notes
- Update `pyproject.toml` if you want stricter dependency pins.
>>>>>>> 5d4151d (added basic piping)

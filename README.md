# Aicashadviser

AICashAdvisor is a deterministic finance assistant. It ingests CSV/PDF statements, normalizes and analyzes transactions, and generates budgets, debt payoff plans, and narrative reports. All calculations are reproducible; no numbers are invented by AI.

## Deploy on Render (Blueprint)

1. Push this repository to GitHub.
2. In Render, choose **New +** → **Blueprint**.
3. Select this repo; Render will detect `render.yaml` and create the web service.
4. Deploy. Render will run `pip install -r requirements.txt` and start with:
   `uvicorn backend.render_app:app --host 0.0.0.0 --port $PORT`
5. Verify health at `/health`.

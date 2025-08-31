# Deploying FastAPI Email Summarizer to Render

## 1. Prerequisites
- Your code is pushed to a public or private GitHub repository.
- You have a Render.com account.

## 2. Ensure these files exist in your repo
- requirements.txt (should include fastapi, uvicorn, sqlalchemy, openai, httpx, etc.)
- .env.example (for reference)
- app/ directory with all backend code
- static/ directory with frontend files

## 3. Add a start command for Render
Render expects a command to start your web service. For FastAPI:
```
uvicorn app.main:app --host 0.0.0.0 --port 10000
```
(Replace `app.main:app` with the correct import path if your main.py is elsewhere.)

## 4. (Optional) Add a render.yaml
You can add a `render.yaml` file for infrastructure-as-code deployment. Example:
```yaml
services:
  - type: web
    name: email-summarizer
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port 10000
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: APP_SECRET_KEY
        sync: false
```

## 5. Set environment variables in Render dashboard
- `OPENAI_API_KEY` (your OpenAI key)
- `APP_SECRET_KEY` (any random string)
- Any other secrets you use

## 6. Deploy on Render
- Go to [Render.com](https://render.com/)
- Click "New Web Service"
- Connect your GitHub repo
- Set the build and start commands as above
- Set environment variables
- Click "Create Web Service"

## 7. Notes
- If you use a custom domain, configure it in Render's dashboard.
- If you need CORS for the frontend, add FastAPI CORS middleware.
- For static files, FastAPI's StaticFiles will serve them at `/static`.

## 8. Test your deployment
- Once deployed, visit the Render-provided URL.
- Log in, connect Gmail, and test all features.

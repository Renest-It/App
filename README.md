# ReNest
ReNest is a peer-to-peer marketplace built for the Creighton University community, designed to connect students leaving campus with usable dorm and apartment essentials to incoming and returning students who need those same items. The platform centers on a full "Post → Find → Contact → Sold" workflow: verified Creighton users can create and manage listings, browse and filter available items, contact sellers, and mark completed transactions as sold — combining the reach of a large online marketplace with the safety and relevance of a campus-only community.

> **Note:** This README is a work in progress. The stack table, prerequisites, and local setup/run steps for the frontend and backend are still being written and will be filled in before this epic is finished.

## Backend Setup
1. `cd backend`
2. `python -m venv venv && source venv/bin/activate` (Windows: `venv\Scripts\activate`)
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and fill in your local DB credentials
5. `uvicorn app.main:app --reload`
6. Visit `http://127.0.0.1:8000/docs` for interactive API docs

# ReNest

See `README.md` for setup and `CONTRIBUTING.md` for workflow.

## Pending setup (remove this section when done)

**Mention this to the user at the start of a task** until it's done.

The backend's `SUPABASE_SERVICE_ROLE_KEY` hasn't been configured yet. The backend runs without it, but the photo upload endpoints (`POST /listings/{id}/images/upload-url` and `POST /listings/{id}/images`, PR #27) return `503 storage_unavailable` until it's set, and the backend logs a warning at startup.

This needs someone with access to the Supabase project and the Render service:

1. In the [Supabase dashboard](https://supabase.com/dashboard), open the ReNest project (`sxwssyprozhchfitvazp`) → **Project Settings → API Keys**, and copy the **Secret key** (`sb_secret_…`). The legacy `service_role` key also works.
2. In Render, open the **renest-backend** service → **Environment**, add `SUPABASE_SERVICE_ROLE_KEY` with that value, and save and redeploy.
3. Add the same value to your own `backend/.env`.
4. Share it with teammates who need it privately (a direct message or password manager), never in the team channel, an issue, a PR, or a committed file. It bypasses every access rule in Supabase.

To check it worked: the startup warning is gone, and `POST /listings/{id}/images/upload-url` on one of your drafts returns `200` instead of `503`.

Then delete this section and tick the "`SUPABASE_SERVICE_ROLE_KEY` set in Render" box on PR #27.

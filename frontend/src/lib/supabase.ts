import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!SUPABASE_URL) {
  throw new Error(
    "VITE_SUPABASE_URL is not set. Copy frontend/.env.example to frontend/.env and set it.",
  );
}

if (!SUPABASE_ANON_KEY) {
  throw new Error(
    "VITE_SUPABASE_ANON_KEY is not set. Copy frontend/.env.example to frontend/.env and set it.",
  );
}

// The only Supabase client in the frontend — import this, never call createClient elsewhere.
// Uses the public anon key; the service-role key must never appear in /frontend.
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

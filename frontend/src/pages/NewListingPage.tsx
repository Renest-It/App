import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { createListing, getCategories } from "../api/client";
import type { Category } from "../api/types";

export function NewListingPage() {
  const navigate = useNavigate();

  const [categories, setCategories] = useState<Category[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCategories()
      .then((cats) => {
        setCategories(cats);
        if (cats.length > 0) {
          setCategoryId(String(cats[0].id));
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load categories"));
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    createListing({
      title,
      description: description || null,
      price_cents: Math.round(Number(price) * 100),
      category_id: Number(categoryId),
    })
      .then(() => {
        navigate("/");
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Something went wrong");
        setSubmitting(false);
      });
  }

  return (
    <div>
      <h1>New Listing</h1>
      {error && <p role="alert">{error}</p>}
      <form onSubmit={handleSubmit}>
        <label>
          Title
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <label>
          Description
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          Price (USD)
          <input
            type="number"
            step="0.01"
            min="0"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
          />
        </label>
        <label>
          Category
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Creating…" : "Create Listing"}
        </button>
      </form>
    </div>
  );
}

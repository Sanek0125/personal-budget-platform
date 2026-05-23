import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="page-card">
      <p className="eyebrow">404</p>
      <h2>Page not found</h2>
      <p>This frontend module is not available yet.</p>
      <Link className="primary-link" to="/">
        Back to dashboard
      </Link>
    </section>
  );
}

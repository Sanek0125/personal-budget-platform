export function FeaturePage({ title, description }: { title: string; description: string }) {
  return (
    <section className="page-card">
      <p className="eyebrow">MVP module</p>
      <h2>{title}</h2>
      <p>{description}</p>
    </section>
  );
}

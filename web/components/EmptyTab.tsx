export default function EmptyTab({ title, message }: { title: string; message: string }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{title}</h2>
      <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
        <p className="text-sm text-blue-900">{message}</p>
      </div>
    </section>
  );
}

import { useEffect, useState } from "react";
import { api, getError, rowsFrom } from "../lib/api";
import {
  Alert,
  DataTable,
  RecordDetails,
  Loading,
  Modal,
  PageHeader,
  SearchBox,
} from "../components/Shared";
export default function Applicants() {
  const [rows, setRows] = useState<any[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<any>(null);
  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/api/applicants?limit=100");
      setRows(rowsFrom(r.data));
    } catch (e) {
      setError(getError(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);
 const filtered = rows.filter((r) => {
  const query = search.trim().toLowerCase();

  if (!query) return true;

  const searchableFields = [
    r.applicant_id,
    r.first_name,
    r.last_name,
    `${r.first_name || ""} ${r.last_name || ""}`,
    r.email,
    r.phone,
  ];

  return searchableFields.some((field) =>
    String(field || "").toLowerCase().includes(query),
  );
});
  return (
    <>
      <PageHeader
        title="Applicants"
        subtitle="Browse applicant master records and inspect individual applicant details."
      />
      <div className="panel p-4">
        <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row">
          <p className="text-sm font-semibold text-slate-600">
            {rows.length} records loaded
          </p>
          <SearchBox value={search} onChange={setSearch} />
        </div>
        {error && <Alert kind="error">{error}</Alert>}
        {loading ? (
          <Loading />
        ) : (
          <DataTable
            rows={filtered}
            onRowClick={setSelected}
            columns={[
              { key: "applicant_id", label: "Applicant ID" },
              { key: "applicant_type", label: "Type" },
              {
                key: "first_name",
                label: "Name",
                render: (r) =>
                  `${r.first_name || ""} ${r.last_name || ""}`.trim(),
              },
              { key: "email", label: "Email" },
              { key: "phone", label: "Phone" },
            ]}
          />
        )}
      </div>
      {selected && (
        <Modal
          title={
            `${selected.first_name || ""} ${selected.last_name || ""}`.trim() ||
            "Applicant profile"
          }
          onClose={() => setSelected(null)}
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 p-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Applicant reference
              </p>
              <p className="text-sm font-semibold text-slate-800">
                {selected.applicant_id}
              </p>
            </div>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
              {String(selected.applicant_status || "ACTIVE").replaceAll(
                "_",
                " ",
              )}
            </span>
          </div>
          <RecordDetails value={selected} />
        </Modal>
      )}
    </>
  );
}

import { useEffect, useState } from "react";
import { Plus, Eye, History, RefreshCw } from "lucide-react";
import { api, getError, rowsFrom, money, dateTime } from "../lib/api";
import {
  Alert,
  DataTable,
  JsonView,
  Loading,
  Modal,
  PageHeader,
  SearchBox,
  StatusPill,
  SearchableLookup,
} from "../components/Shared";
export default function Quotes({ user }: { user: any }) {
  const [rows, setRows] = useState<any[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [modal, setModal] = useState(""),
    [selected, setSelected] = useState<any>(null),
    [detail, setDetail] = useState<any>(null);
  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/api/quotes?limit=100");
      setRows(rowsFrom(r.data, "quotes"));
      setError("");
    } catch (e) {
      setError(getError(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);
  const inspect = async (id: string, kind: "detail" | "audit") => {
    try {
      const r = await api.get(
        kind === "detail"
          ? `/api/quotes/${id}`
          : `/api/quotes/${id}/audit-history`,
      );
      setDetail(r.data);
      setModal(kind);
    } catch (e) {
      setError(getError(e));
    }
  };
  const filtered = rows.filter((r) =>
    JSON.stringify(r).toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeader
        title="Quotes"
        subtitle="Track submissions, calculated premiums, lifecycle status and quote-level audit trails."
        action={
          <button className="btn-secondary" onClick={load}>
            <RefreshCw size={15} /> Refresh
          </button>
        }
      />
      {error && <Alert kind="error">{error}</Alert>}
      <div className="panel p-4">
        <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row">
          <p className="text-sm font-semibold text-slate-600">
            {rows.length} quotes loaded
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <SearchBox value={search} onChange={setSearch} />
            {["ADMIN", "OPERATIONS_ANALYST"].includes(user.role) && (
              <button
                className="btn-primary"
                onClick={() => {
                  setSelected(null);
                  setModal("create");
                }}
              >
                <Plus size={16} /> Create quote
              </button>
            )}
          </div>
        </div>
        {loading ? (
          <Loading />
        ) : (
          <DataTable
            rows={filtered}
            columns={[
              { key: "quote_id", label: "Quote ID" },
              { key: "applicant_id", label: "Applicant" },
              { key: "product_id", label: "Product" },
              {
                key: "quote_status",
                label: "Status",
                render: (r) => <StatusPill value={r.quote_status} />,
              },
              {
                key: "calculated_premium",
                label: "Premium",
                render: (r) => money(r.calculated_premium, r.currency || "INR"),
              },
              {
                key: "created_at",
                label: "Created",
                render: (r) => dateTime(r.created_at),
              },
              {
                key: "actions",
                label: "Actions",
                render: (r) => (
                  <div className="flex gap-1">
                    <button
                      title="Details"
                      onClick={(e) => {
                        e.stopPropagation();
                        inspect(r.quote_id, "detail");
                      }}
                      className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"
                    >
                      <Eye size={15} />
                    </button>
                    <button
                      title="Audit history"
                      onClick={(e) => {
                        e.stopPropagation();
                        inspect(r.quote_id, "audit");
                      }}
                      className="rounded-lg p-2 text-teal hover:bg-teal/10"
                    >
                      <History size={15} />
                    </button>
                  </div>
                ),
              },
            ]}
          />
        )}
      </div>
      {user.role === "ADMIN" && (
        <QuoteActions onError={setError} onDone={load} />
      )}
      {modal === "detail" && detail && (
        <Modal
          title={`Quote ${detail.quote?.quote_id || ""}`}
          onClose={() => setModal("")}
        >
          <JsonView value={detail} />
        </Modal>
      )}
      {modal === "audit" && detail && (
        <Modal
          title={`Audit history · ${detail.quote_id}`}
          onClose={() => setModal("")}
        >
          <p className="mb-3 text-xs text-slate-500">
            {detail.total_quote_events} quote events ·{" "}
            {detail.total_underwriting_decisions} decisions ·{" "}
            {detail.total_risk_assessments} risk assessments
          </p>
          <div className="space-y-3">
            {(detail.audit_timeline || []).map((x: any, i: number) => (
              <div
                key={i}
                className="relative border-l-2 border-teal/20 pb-3 pl-4"
              >
                <span className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-teal" />
                <p className="text-sm font-bold">
                  {String(x.event_type || "Event").replaceAll("_", " ")}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {dateTime(x.timestamp)} ·{" "}
                  {x.actor_reference || x.reviewer_reference || x.source}
                </p>
                {x.decision_reason && (
                  <p className="mt-1 text-xs text-slate-600">
                    {x.decision_reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Modal>
      )}
      {modal === "create" && (
        <CreateQuote
          onClose={() => setModal("")}
          onDone={() => {
            setModal("");
            load();
          }}
        />
      )}
    </>
  );
}
function CreateQuote({
  onClose,
  onDone,
}: {
  onClose: () => void;
  onDone: () => void;
}) {
  const [form, setForm] = useState<any>({
    applicant_id: "",
    asset_id: "",
    product_id: "",
    requested_start_date: "",
    requested_end_date: "",
    coverage_option_id: "",
    selected_limit: "",
    risk_observations: "",
  });
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<any>(null);
  const set = (k: string, v: string) => setForm((f: any) => ({ ...f, [k]: v }));
  const submit = async (e: any) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const observations = Object.fromEntries(
        form.risk_observations
          .split("\n")
          .map((line: string) => line.trim())
          .filter(Boolean)
          .map((line: string) => {
            const i = line.indexOf(":");
            if (i < 1)
              throw new Error(
                "Enter each observation as Field: value on a separate line.",
              );
            const key = line.slice(0, i).trim(),
              raw = line.slice(i + 1).trim();
            if (!key || !raw)
              throw new Error(
                "Each observation needs both a field name and a value.",
              );
            const value =
              raw.toLowerCase() === "true"
                ? true
                : raw.toLowerCase() === "false"
                  ? false
                  : raw !== "" && !Number.isNaN(Number(raw))
                    ? Number(raw)
                    : raw;
            return [key, value];
          }),
      );
      const payload = {
        applicant_id: form.applicant_id,
        asset_id: form.asset_id,
        product_id: form.product_id,
        requested_start_date: form.requested_start_date,
        requested_end_date: form.requested_end_date,
        coverages: [
          {
            coverage_option_id: form.coverage_option_id,
            selected_limit: Number(form.selected_limit),
          },
        ],
        risk_observations: observations,
      };
      const r = await api.post("/api/quotes", payload);
      setResult(r.data);
    } catch (e) {
      setError(getError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title="Create an insurance quote" onClose={onClose}>
      {result ? (
        <>
          <Alert kind="success">Quote created successfully.</Alert>
          <JsonView value={result} />
          <button className="btn-primary mt-4" onClick={onDone}>
            Return to quotes
          </button>
        </>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert kind="error">{error}</Alert>}
          <div className="grid gap-3 sm:grid-cols-2">
            <label>
              <span className="field-label">Applicant</span>
              <SearchableLookup
  kind="applicants"
  value={form.applicant_id}
  onChange={id => {
    setForm((f: any) => ({
      ...f,
      applicant_id: id,
      asset_id: '',
    }))
  }}
  placeholder="Search applicant name or email"
/>
            </label>
            <label>
              <span className="field-label">Insured asset</span>
              <SearchableLookup
  kind="assets"
  value={form.asset_id}
  onChange={id => set('asset_id', id)}
  filterBy={form.applicant_id}
  filterKey="applicant_id"
  disabled={!form.applicant_id}
  placeholder={
    form.applicant_id
      ? "Search this applicant's assets"
      : "Select applicant first"
  }
/>
            </label>
            <label>
              <span className="field-label">Insurance product</span>
              <SearchableLookup
                kind="products"
                value={form.product_id}
                onChange={(id) => {
                  set("product_id", id);
                  set("coverage_option_id", "");
                }}
                placeholder="Search product name or code"
              />
            </label>
            <label>
              <span className="field-label">Coverage option</span>
              <SearchableLookup
                kind="coverage-options"
                value={form.coverage_option_id}
                onChange={(id) => set("coverage_option_id", id)}
                filterBy={form.product_id}
                placeholder="Search coverage option"
              />
            </label>
            <label>
              <span className="field-label">Selected coverage limit</span>
              <input
                required
                type="number"
                min="1"
                step="0.01"
                className="field"
                value={form.selected_limit}
                onChange={(e) => set("selected_limit", e.target.value)}
              />
            </label>
            <label>
              <span className="field-label">Start date</span>
              <input
                required
                type="date"
                className="field"
                value={form.requested_start_date}
                onChange={(e) => set("requested_start_date", e.target.value)}
              />
            </label>
            <label>
              <span className="field-label">End date</span>
              <input
                required
                type="date"
                className="field"
                value={form.requested_end_date}
                onChange={(e) => set("requested_end_date", e.target.value)}
              />
            </label>
          </div>
          <label>
            <span className="field-label">
              Additional risk observations (optional)
            </span>
            <textarea
              rows={3}
              className="field"
              placeholder={"Example: vehicle_age: 5\nclaims_last_3_years: 1"}
              value={form.risk_observations}
              onChange={(e) => set("risk_observations", e.target.value)}
            />
            <span className="mt-1 block text-xs text-slate-500">
              Enter one observation per line as Field: value. Leave blank if
              there are no additional observations.
            </span>
          </label>
          <p className="text-xs leading-5 text-slate-500">
            Coverage options are loaded from your existing database. The
            selected option must belong to the product you enter.
          </p>
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button disabled={busy} className="btn-primary">
              {busy ? "Creating…" : "Create quote"}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function QuoteActions({
  onError,
  onDone,
}: {
  onError: (s: string) => void;
  onDone: () => void;
}) {
  const [quoteId, setQuoteId] = useState(""),
    [customerRef, setCustomerRef] = useState(""),
    [amount, setAmount] = useState(""),
    [paymentRef, setPaymentRef] = useState(""),
    [paymentId, setPaymentId] = useState(""),
    [verifierRef, setVerifierRef] = useState(""),
    [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<any>) => {
    setBusy(true);
    onError("");
    try {
      await fn();
      onDone();
    } catch (e) {
      onError(getError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="panel mt-5 p-5">
      <h2 className="font-display font-bold">
        Quote acceptance and payment actions
      </h2>
      <p className="mt-1 text-xs text-slate-500">
        Use an existing quote reference. Actions call the existing acceptance
        and payment APIs.
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label>
          <span className="field-label">Quote ID</span>
          <input
            className="field"
            value={quoteId}
            onChange={(e) => setQuoteId(e.target.value)}
            placeholder="QTE-2026-…"
          />
        </label>
        <label>
          <span className="field-label">Customer reference</span>
          <input
            className="field"
            value={customerRef}
            onChange={(e) => setCustomerRef(e.target.value)}
            placeholder="Customer acceptance reference"
          />
        </label>
      </div>
      <button
        className="btn-secondary mt-3"
        disabled={busy || !quoteId || !customerRef}
        onClick={() =>
          run(() =>
            api.post(`/api/quotes/${quoteId}/accept`, {
              customer_reference: customerRef,
            }),
          )
        }
      >
        Accept quote
      </button>
      <div className="mt-5 grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-2">
        <label>
          <span className="field-label">Payment amount</span>
          <input
            className="field"
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>
        <label>
          <span className="field-label">Payment reference</span>
          <input
            className="field"
            value={paymentRef}
            onChange={(e) => setPaymentRef(e.target.value)}
          />
        </label>
      </div>
      <button
        className="btn-secondary mt-3"
        disabled={busy || !quoteId || !amount || !paymentRef}
        onClick={() =>
          run(() =>
            api
              .post(`/api/quotes/${quoteId}/payments`, {
                amount: Number(amount),
                payment_reference: paymentRef,
              })
              .then((r) => {
                if (r.data?.payment_id) setPaymentId(r.data.payment_id);
              }),
          )
        }
      >
        Record payment
      </button>
      <div className="mt-5 grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-2">
        <label>
          <span className="field-label">Payment ID</span>
          <input
            className="field"
            value={paymentId}
            onChange={(e) => setPaymentId(e.target.value)}
            placeholder="Returned after payment creation"
          />
        </label>
        <label>
          <span className="field-label">Verifier reference</span>
          <input
            className="field"
            value={verifierRef}
            onChange={(e) => setVerifierRef(e.target.value)}
          />
        </label>
      </div>
      <button
        className="btn-primary mt-3"
        disabled={busy || !paymentId || !verifierRef}
        onClick={() =>
          run(() =>
            api.post(`/api/payments/${paymentId}/confirm`, {
              verifier_reference: verifierRef,
            }),
          )
        }
      >
        {busy ? "Processing…" : "Confirm payment"}
      </button>
    </div>
  );
}

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
        <QuoteActions quotes={rows} onError={setError} onDone={load} />
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
  quotes,
  onError,
  onDone,
}: {
  quotes: any[];
  onError: (s: string) => void;
  onDone: () => void;
}) {
  const [quoteId, setQuoteId] = useState("");
  const [customerRef, setCustomerRef] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentRef, setPaymentRef] = useState("");
  const [paymentId, setPaymentId] = useState("");
  const [pendingPayments, setPendingPayments] = useState<any[]>([]);
  const [verifierRef, setVerifierRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [paymentLoading, setPaymentLoading] = useState(false);

  const approvedQuotes = quotes.filter(
    (q) => q.quote_status === "APPROVED" && !q.applicant_accepted_at,
  );
  const acceptedQuotes = quotes.filter(
    (q) => q.quote_status === "ACCEPTED",
  );

  const selectedQuote = quotes.find((q) => q.quote_id === quoteId);

  const loadPendingPayments = async () => {
    setPaymentLoading(true);
    try {
      const response = await api.get("/api/payments?status=PENDING&limit=100");
      setPendingPayments(rowsFrom(response.data, "payments"));
    } catch (e) {
      onError(getError(e));
    } finally {
      setPaymentLoading(false);
    }
  };

  useEffect(() => {
    loadPendingPayments();
  }, []);

  useEffect(() => {
    if (selectedQuote) {
      setPaymentAmount(String(selectedQuote.calculated_premium ?? ""));
    } else {
      setPaymentAmount("");
    }
  }, [quoteId, quotes]);

  const run = async (fn: () => Promise<any>) => {
    setBusy(true);
    onError("");
    try {
      const response = await fn();
      if (response?.data?.payment_id) {
        setPaymentId(response.data.payment_id);
      }
      await onDone();
      await loadPendingPayments();
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
        Select existing quotes and pending payments. Premium and payment IDs
        are loaded from the database; reference fields are entered by the user.
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label>
          <span className="field-label">Approved quote</span>
          <select
            className="field"
            value={quoteId}
            onChange={(e) => setQuoteId(e.target.value)}
            disabled={busy}
          >
            <option value="">Select an approved quote</option>
            {approvedQuotes.map((q) => (
              <option key={q.quote_id} value={q.quote_id}>
                {q.quote_id} — {money(q.calculated_premium, q.currency || "INR")}
              </option>
            ))}
          </select>
          {approvedQuotes.length === 0 && (
            <span className="mt-1 block text-xs text-slate-500">
              No approved quotes are available in the currently loaded records.
            </span>
          )}
        </label>
        <label>
          <span className="field-label">Customer acceptance reference</span>
          <input
            className="field"
            value={customerRef}
            onChange={(e) => setCustomerRef(e.target.value)}
            placeholder="Enter customer reference"
            disabled={busy}
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
        {busy ? "Processing…" : "Accept quote"}
      </button>

      <div className="mt-5 grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-2">
        <label>
          <span className="field-label">Accepted quote</span>
          <select
            className="field"
            value={acceptedQuotes.some((q) => q.quote_id === quoteId) ? quoteId : ""}
            onChange={(e) => setQuoteId(e.target.value)}
            disabled={busy}
          >
            <option value="">Select an accepted quote</option>
            {acceptedQuotes.map((q) => (
              <option key={q.quote_id} value={q.quote_id}>
                {q.quote_id} — {money(q.calculated_premium, q.currency || "INR")}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Payment amount</span>
          <input
            className="field"
            type="number"
            min="0.01"
            step="0.01"
            value={paymentAmount}
            readOnly
            placeholder="Select an accepted quote"
          />
        </label>
        <label className="md:col-span-2">
          <span className="field-label">Simulated payment reference</span>
          <input
            className="field"
            value={paymentRef}
            onChange={(e) => setPaymentRef(e.target.value)}
            placeholder="Enter simulated payment reference"
            disabled={busy}
          />
        </label>
      </div>
      <button
        className="btn-secondary mt-3"
        disabled={
          busy ||
          !acceptedQuotes.some((q) => q.quote_id === quoteId) ||
          !paymentAmount ||
          !paymentRef
        }
        onClick={() =>
          run(() =>
            api.post(`/api/quotes/${quoteId}/payments`, {
              amount: Number(paymentAmount),
              payment_reference: paymentRef,
            }),
          )
        }
      >
        {busy ? "Processing…" : "Record payment"}
      </button>

      <div className="mt-5 grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-2">
        <label>
          <span className="field-label">Pending payment</span>
          <select
            className="field"
            value={paymentId}
            onChange={(e) => setPaymentId(e.target.value)}
            disabled={busy || paymentLoading}
          >
            <option value="">
              {paymentLoading ? "Loading pending payments…" : "Select a pending payment"}
            </option>
            {pendingPayments.map((p) => (
              <option key={p.payment_id} value={p.payment_id}>
                {p.payment_id} — {p.quote_id} — {money(p.amount, p.currency || "INR")}
              </option>
            ))}
          </select>
          {!paymentLoading && pendingPayments.length === 0 && (
            <span className="mt-1 block text-xs text-slate-500">
              No pending payments found.
            </span>
          )}
        </label>
        <label>
          <span className="field-label">Verifier reference</span>
          <input
            className="field"
            value={verifierRef}
            onChange={(e) => setVerifierRef(e.target.value)}
            placeholder="Enter operations verification reference"
            disabled={busy}
          />
        </label>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          className="btn-secondary"
          type="button"
          onClick={loadPendingPayments}
          disabled={busy || paymentLoading}
        >
          {paymentLoading ? "Refreshing…" : "Refresh pending payments"}
        </button>
        <button
          className="btn-primary"
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
    </div>
  );
}

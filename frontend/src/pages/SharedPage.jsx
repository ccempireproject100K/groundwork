import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

// Public view for a portfolio share link (backend: GET /p/{token}, noindex).
// The member mints the link from their Journey portfolio and can revoke it
// at any time; a revoked or unknown token shows the honest missing note.
export default function SharedPage() {
  const { t } = useTranslation();
  const { token } = useParams();
  const [item, setItem] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`/p/${token}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then((d) => { if (alive) setItem(d.item || null); })
      .catch(() => { if (alive) setFailed(true); });
    return () => { alive = false; };
  }, [token]);

  return (
    <section className="page">
      <h1>{t("gap.sharedTitle")}</h1>
      {failed || item === null ? (
        failed ? <p className="notice">{t("gap.sharedMissing")}</p> : null
      ) : (
        <div className="card">
          <h2>{item.title}</h2>
          {item.story && <p>{item.story}</p>}
          {item.milestone_day && <p>{t("journey.milestoneDays")}: {item.milestone_day}</p>}
          {item.happened_on && <p>{item.happened_on}</p>}
        </div>
      )}
    </section>
  );
}

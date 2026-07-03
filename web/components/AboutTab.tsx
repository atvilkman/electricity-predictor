"use client";
import { useLanguage } from "@/lib/i18n";

export default function AboutTab() {
  const { t } = useLanguage();
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm space-y-10">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900 mb-2">{t("aboutHeading")}</h2>
        <p className="text-gray-600">{t("aboutIntro")}</p>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutForecastTitle")}</h3>
        <p className="text-gray-700 leading-relaxed">{t("aboutForecastP1")}</p>
        <p className="text-gray-700 leading-relaxed">{t("aboutForecastP2")}</p>
        <p className="text-gray-700 leading-relaxed">{t("aboutForecastP3")}</p>
        <p className="text-gray-700 leading-relaxed">{t("aboutForecastP4")}</p>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutVsActualTitle")}</h3>
        <p className="text-gray-700 leading-relaxed">{t("aboutVsActualP1")}</p>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutAccuracyTitle")}</h3>
        <p className="text-gray-700 leading-relaxed">{t("aboutAccuracyP1")}</p>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutSignalsTitle")}</h3>
        <p className="text-gray-700 leading-relaxed">{t("aboutSignalsP1")}</p>
        <p className="text-gray-700 leading-relaxed">{t("aboutSignalsP2")}</p>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutGridTitle")}</h3>
        <p className="text-gray-700 leading-relaxed">{t("aboutGridP1")}</p>
        <ul className="list-disc list-inside text-gray-700 space-y-1 pl-2">
          <li><span className="font-medium">{t("aboutGridLoad")}</span></li>
          <li><span className="font-medium">{t("aboutGridGen")}</span></li>
          <li><span className="font-medium">{t("aboutGridFlows")}</span></li>
          <li><span className="font-medium">{t("aboutGridSustain")}</span></li>
        </ul>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutAiTitle")}</h3>
        <p className="text-gray-700 leading-relaxed">{t("aboutAiP1")}</p>
        <p className="text-gray-700 leading-relaxed">{t("aboutAiP2")}</p>
        <p className="text-gray-700 leading-relaxed">{t("aboutAiP3")}</p>
        <p className="text-gray-700 leading-relaxed">{t("aboutAiP4")}</p>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutLimitationsTitle")}</h3>
        <ul className="list-disc list-inside text-gray-700 space-y-1 pl-2">
          <li>{t("aboutLimit1")}</li>
          <li>{t("aboutLimit2")}</li>
          <li>{t("aboutLimit3")}</li>
          <li>{t("aboutLimit4")}</li>
          <li>{t("aboutLimit5")}</li>
        </ul>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold text-gray-900">{t("aboutRefreshTitle")}</h3>
        <p className="text-gray-700 leading-relaxed">{t("aboutRefreshP1")}</p>
      </div>
    </section>
  );
}

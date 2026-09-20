import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";


import { Button } from "@/components/ui/button";
import { api, type PathUnit } from "@/lib/api";
import { usePlayer } from "@/store/player";

import { LessonButton } from "./lesson-button";
import { UnitBanner } from "./unit-banner";

const mascotSad = "/assets/mascot_sad.svg";

type LearnProps = {
  onStart: (params: { campaign?: string; topic?: string }) => void;
};

export const Learn = ({ onStart }: LearnProps) => {
  const campaign = usePlayer((state) => state.campaign);
  const [units, setUnits] = useState<PathUnit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.path(campaign || undefined);
      setUnits(data.units);
      setError(null);
    } catch {
      setError("Could not load your path.");
    }
  }, [campaign]);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <img src={mascotSad} alt="" aria-hidden width={80} height={80} />
        <p className="font-bold text-neutral-700">{error}</p>
        <Button variant="primary" onClick={() => void load()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!units) return <p className="py-20 text-center text-sm text-slate-400">Loading your path…</p>;

  if (!units.length) {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <img src={mascotSad} alt="" aria-hidden width={80} height={80} />
        <p className="max-w-xs font-bold text-neutral-700">
          No material yet. Import notes or a PDF and Intellect builds the path for you.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-10 pb-10">
      {units.map((unit) => (
        <section key={unit.material_id} className="space-y-2">
          <UnitBanner
            title={unit.title}
            course={unit.course ?? unit.campaign}
            examTitle={unit.exam_title}
            daysLeft={unit.days_left}
            onContinue={() => onStart({ campaign: unit.campaign })}
          />

          <div className="relative flex flex-col items-center">
            {unit.nodes.map((node, index) => (
              <LessonButton
                key={`${unit.material_id}-${node.topic}`}
                index={index}
                totalCount={unit.nodes.length}
                locked={node.state === "locked"}
                current={node.state === "current"}
                percentage={Math.round(node.mastery * 100)}
                label={`${node.topic} · ${Math.round(node.mastery * 100)}% mastered`}
                onClick={() => {
                  if (node.state === "locked") {
                    toast("Finish the node above first.");
                    return;
                  }
                  onStart({ campaign: unit.campaign, topic: node.topic });
                }}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
};

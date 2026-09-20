import { Card } from "./card";

type ChallengeProps = {
  options: string[];
  onSelect: (index: number) => void;
  status: "correct" | "wrong" | "none";
  selectedOption?: number;
  disabled?: boolean;
};

export const Challenge = ({ options, onSelect, status, selectedOption, disabled }: ChallengeProps) => {
  return (
    /* One column, not the original two. These options are full sentences of
       mathematics, not single words, and a two-up grid shreds them. */
    <div className="grid grid-cols-1 gap-2">
      {options.map((option, i) => (
        <Card
          key={`${i}-${option.slice(0, 24)}`}
          text={option}
          shortcut={`${i + 1}`}
          selected={selectedOption === i}
          onClick={() => onSelect(i)}
          status={status}
          disabled={disabled}
        />
      ))}
    </div>
  );
};

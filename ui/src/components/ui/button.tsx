import * as React from "react";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-xl text-sm font-bold ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 uppercase tracking-wide",
  {
    variants: {
      variant: {
        /* On a dark canvas a filled button carries dark ink, because the fill
           is the bright surface. Inverting that gives light-on-light, which
           reads as a disabled control. */
        default:
          "bg-surface text-ink-muted border-line border-2 border-b-4 active:border-b-2 hover:bg-surface-hover",

        locked:
          "bg-surface-raised text-ink-faint hover:bg-surface-raised border-line-strong border-b-4 active:border-b-0 cursor-not-allowed",

        primary:
          "lift-accent bg-accent text-accent-ink hover:brightness-110 border-0 active:translate-y-px",
        primaryOutline: "bg-transparent text-accent border-2 border-accent/40 hover:bg-accent/10",

        secondary:
          "lift-accent bg-correct text-accent-ink hover:brightness-110 border-0 active:translate-y-px",
        secondaryOutline: "bg-transparent text-correct border-2 border-correct/40 hover:bg-correct/10",

        danger:
          "bg-wrong text-accent-ink shadow-[0_6px_18px_-6px_hsl(var(--wrong)/0.55)] hover:brightness-110 border-0 active:translate-y-px",
        dangerOutline: "bg-transparent text-wrong border-2 border-wrong/40 hover:bg-wrong/10",

        super:
          "bg-indigo-400 text-accent-ink hover:bg-indigo-400/90 border-indigo-600 border-b-4 active:border-b-0",
        superOutline: "bg-transparent text-indigo-300 border-2 border-indigo-400/40 hover:bg-indigo-400/10",

        ghost:
          "bg-transparent text-ink-muted border-transparent border-0 hover:bg-surface-raised hover:text-ink",

        sidebar:
          "bg-transparent text-ink-muted border-2 border-transparent hover:bg-surface-raised transition-none",
        sidebarOutline:
          "bg-accent/15 text-accent border-accent/40 border-2 hover:bg-accent/20 transition-none",
      },
      size: {
        default: "h-11 px-4 py-2",
        sm: "h-9 px-3",
        lg: "h-12 px-8",
        icon: "h-10 w-10",

        // custom
        rounded: "rounded-full",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };

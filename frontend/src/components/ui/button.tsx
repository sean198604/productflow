import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-[13px] font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-[#1a365d] text-white shadow-[0_1px_2px_rgba(26,54,93,0.25)] hover:bg-[#16345f]",
        secondary:
          "border border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50",
        ghost: "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
        danger: "bg-red-600 text-white hover:bg-red-700",
      },
    },
    defaultVariants: {
      variant: "primary",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export function Button({ className, variant, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant }), className)}
      {...props}
    />
  );
}

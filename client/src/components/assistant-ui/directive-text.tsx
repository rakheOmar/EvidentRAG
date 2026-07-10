"use client";

import type {
  TextMessagePartComponent,
  Unstable_DirectiveFormatter,
} from "@assistant-ui/react";
import { unstable_defaultDirectiveFormatter } from "@assistant-ui/react";
import { type FC, memo } from "react";
import { Badge } from "./badge";

type IconComponent = FC<{ className?: string }>;

export type CreateDirectiveTextOptions = {
  /** Maps a directive `type` to an icon component. */
  iconMap?: Record<string, IconComponent>;
  /** Icon rendered when `iconMap` has no entry for the segment type. */
  fallbackIcon?: IconComponent;
};

/** Creates a `Text` message part component that parses directive syntax and renders inline chips. */
export function createDirectiveText(
  formatter: Unstable_DirectiveFormatter,
  options?: CreateDirectiveTextOptions,
): TextMessagePartComponent {
  const iconMap = options?.iconMap;
  const fallbackIcon = options?.fallbackIcon;

  const Component: TextMessagePartComponent = ({ text }) => {
    const segments = formatter.parse(text);

    if (segments.length === 1 && segments[0]!.kind === "text") {
      return <>{text}</>;
    }

    return (
      <>
        {segments.map((seg, i) => {
          if (seg.kind === "text") {
            return (
              <span className="whitespace-pre-wrap" key={i}>
                {seg.text}
              </span>
            );
          }

          const Icon = iconMap?.[seg.type] ?? fallbackIcon;
          return (
            <Badge
              aria-label={`${seg.type}: ${seg.label}`}
              className="aui-directive-chip items-baseline text-[13px] leading-none [&_svg]:self-center"
              data-directive-id={seg.id}
              data-directive-type={seg.type}
              data-slot="directive-text-chip"
              key={i}
              size="sm"
              variant="info"
            >
              {Icon && <Icon />}
              {seg.label}
            </Badge>
          );
        })}
      </>
    );
  };
  Component.displayName = "DirectiveText";
  return Component;
}

const DirectiveTextImpl = createDirectiveText(
  unstable_defaultDirectiveFormatter,
);

/** `Text` message part component that renders directive syntax as inline chips. */
export const DirectiveText: TextMessagePartComponent = memo(DirectiveTextImpl);

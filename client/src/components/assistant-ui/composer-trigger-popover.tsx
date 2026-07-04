"use client";

import {
  ComposerPrimitive,
  type Unstable_DirectiveFormatter,
  type Unstable_TriggerItem,
  unstable_defaultDirectiveFormatter,
  unstable_useTriggerPopoverScopeContext,
} from "@assistant-ui/react";
import { ChevronLeftIcon, ChevronRightIcon, SparklesIcon } from "lucide-react";
import { type ComponentPropsWithoutRef, type FC, memo, useRef } from "react";
import { cn } from "@/lib/utils";

type IconComponent = FC<{ className?: string }>;

type DirectiveBehaviorProps = {
  /** Formatter used to serialize the selected item into composer text. */
  formatter?: Unstable_DirectiveFormatter | undefined;
  /** Called after the directive text has been inserted into the composer. */
  onInserted?: ((item: Unstable_TriggerItem) => void) | undefined;
};

type ActionBehaviorProps = {
  /** Formatter used to serialize the audit-trail chip (when `removeOnExecute` is false). */
  formatter?: Unstable_DirectiveFormatter | undefined;
  /** Invoked with the selected item at the moment of selection. */
  onExecute: (item: Unstable_TriggerItem) => void;
  /** If `true`, strip the trigger text from the composer after executing. @default false */
  removeOnExecute?: boolean | undefined;
};

type ComposerTriggerPopoverBaseProps = Omit<
  ComponentPropsWithoutRef<typeof ComposerPrimitive.Unstable_TriggerPopover>,
  "children"
> & {
  /**
   * Maps icon keys to components. Items look up via `item.metadata?.icon`
   * (string); categories look up via their `id`.
   */
  iconMap?: Record<string, IconComponent>;
  /** Fallback icon when no entry in `iconMap` matches. */
  fallbackIcon?: IconComponent;
  /** Label shown on the back button. @default "Back" */
  backLabel?: string;
  /** Label shown when no categories are available. @default "No items available" */
  emptyCategoriesLabel?: string;
  /** Label shown when no items match. @default "No matching items" */
  emptyItemsLabel?: string;
  /** Label shown while an async adapter is resolving items. @default "Loading…" */
  loadingLabel?: string;
};

type ComposerTriggerPopoverProps = ComposerTriggerPopoverBaseProps &
  (
    | {
        /** Insert-directive behavior. */
        directive: DirectiveBehaviorProps;
        action?: never;
      }
    | {
        /** Action behavior. */
        action: ActionBehaviorProps;
        directive?: never;
      }
  );

function resolveIcon(
  iconKey: string | undefined,
  iconMap: Record<string, IconComponent> | undefined,
  fallback: IconComponent
): IconComponent {
  if (iconKey && iconMap?.[iconKey]) {
    return iconMap[iconKey]!;
  }
  return fallback;
}

type CategoriesProps = {
  iconMap: Record<string, IconComponent> | undefined;
  fallbackIcon: IconComponent;
  emptyLabel: string;
};

const Categories: FC<CategoriesProps> = ({
  iconMap,
  fallbackIcon,
  emptyLabel,
}) => (
  <ComposerPrimitive.Unstable_TriggerPopoverCategories>
    {(categories) => (
      <div
        className="flex flex-col py-1"
        data-slot="composer-trigger-popover-categories"
      >
        {categories.map((cat) => {
          const Icon = resolveIcon(cat.id, iconMap, fallbackIcon);
          return (
            <ComposerPrimitive.Unstable_TriggerPopoverCategoryItem
              categoryId={cat.id}
              className="flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm outline-none transition-colors hover:bg-accent focus:bg-accent data-[highlighted]:bg-accent"
              key={cat.id}
            >
              <span className="flex items-center gap-2">
                <Icon className="size-4 text-muted-foreground" />
                {cat.label}
              </span>
              <ChevronRightIcon className="size-4 text-muted-foreground" />
            </ComposerPrimitive.Unstable_TriggerPopoverCategoryItem>
          );
        })}
        {categories.length === 0 && (
          <div className="px-3 py-2 text-muted-foreground text-sm">
            {emptyLabel}
          </div>
        )}
      </div>
    )}
  </ComposerPrimitive.Unstable_TriggerPopoverCategories>
);

type ItemsProps = {
  iconMap: Record<string, IconComponent> | undefined;
  fallbackIcon: IconComponent;
  backLabel: string;
  emptyLabel: string;
  loadingLabel: string;
};

const Items: FC<ItemsProps> = ({
  iconMap,
  fallbackIcon,
  backLabel,
  emptyLabel,
  loadingLabel,
}) => {
  const { isLoading } = unstable_useTriggerPopoverScopeContext();
  return (
    <ComposerPrimitive.Unstable_TriggerPopoverItems>
      {(items) => (
        <div
          className="flex flex-col"
          data-slot="composer-trigger-popover-items"
        >
          <ComposerPrimitive.Unstable_TriggerPopoverBack className="flex cursor-pointer items-center gap-1.5 border-b px-3 py-2 text-muted-foreground text-xs uppercase tracking-wide transition-colors hover:bg-accent">
            <ChevronLeftIcon className="size-3.5" />
            {backLabel}
          </ComposerPrimitive.Unstable_TriggerPopoverBack>

          <div className="py-1">
            {items.map((item, index) => {
              const iconKey =
                typeof item.metadata?.icon === "string"
                  ? item.metadata.icon
                  : undefined;
              const Icon = resolveIcon(iconKey, iconMap, fallbackIcon);
              return (
                <ComposerPrimitive.Unstable_TriggerPopoverItem
                  className="flex w-full cursor-pointer flex-col items-start gap-0.5 px-3 py-2 text-start outline-none transition-colors hover:bg-accent focus:bg-accent data-[highlighted]:bg-accent"
                  index={index}
                  item={item}
                  key={item.id}
                >
                  <span className="flex items-center gap-2 font-medium text-sm">
                    <Icon className="size-3.5 text-primary" />
                    {item.label}
                  </span>
                  {item.description && (
                    <span className="ms-5.5 text-muted-foreground text-xs leading-tight">
                      {item.description}
                    </span>
                  )}
                </ComposerPrimitive.Unstable_TriggerPopoverItem>
              );
            })}
            {items.length === 0 && (
              <div className="px-3 py-2 text-muted-foreground text-sm">
                {isLoading ? loadingLabel : emptyLabel}
              </div>
            )}
          </div>
        </div>
      )}
    </ComposerPrimitive.Unstable_TriggerPopoverItems>
  );
};

/**
 * Pre-built popover UI for a trigger-driven picker (mentions, slash commands, etc).
 * Pass exactly one of `directive` (inserts a chip) or `action` (fires a handler).
 */
const ComposerTriggerPopoverImpl: FC<ComposerTriggerPopoverProps> = ({
  iconMap,
  fallbackIcon = SparklesIcon,
  backLabel = "Back",
  emptyCategoriesLabel = "No items available",
  emptyItemsLabel = "No matching items",
  loadingLabel = "Loading…",
  className,
  directive,
  action,
  ...props
}) => {
  const warnedRef = useRef(false);
  if (
    process.env.NODE_ENV !== "production" &&
    !warnedRef.current &&
    Boolean(directive) === Boolean(action)
  ) {
    warnedRef.current = true;
    console.warn(
      "[assistant-ui] ComposerTriggerPopover requires exactly one of `directive` or `action` props."
    );
  }

  return (
    <ComposerPrimitive.Unstable_TriggerPopover
      className={cn(
        "aui-composer-trigger-popover absolute start-0 bottom-full z-50 mb-2 w-64 overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-lg",
        className
      )}
      data-slot="composer-trigger-popover"
      {...props}
    >
      {directive ? (
        <ComposerPrimitive.Unstable_TriggerPopover.Directive
          formatter={directive.formatter ?? unstable_defaultDirectiveFormatter}
          onInserted={directive.onInserted}
        />
      ) : action ? (
        <ComposerPrimitive.Unstable_TriggerPopover.Action
          formatter={action.formatter ?? unstable_defaultDirectiveFormatter}
          onExecute={action.onExecute}
          removeOnExecute={action.removeOnExecute}
        />
      ) : null}
      <Categories
        emptyLabel={emptyCategoriesLabel}
        fallbackIcon={fallbackIcon}
        iconMap={iconMap}
      />
      <Items
        backLabel={backLabel}
        emptyLabel={emptyItemsLabel}
        fallbackIcon={fallbackIcon}
        iconMap={iconMap}
        loadingLabel={loadingLabel}
      />
    </ComposerPrimitive.Unstable_TriggerPopover>
  );
};
ComposerTriggerPopoverImpl.displayName = "ComposerTriggerPopover";

export const ComposerTriggerPopover = memo(
  ComposerTriggerPopoverImpl
) as FC<ComposerTriggerPopoverProps>;

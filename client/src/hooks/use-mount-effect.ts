/* eslint-disable no-restricted-syntax */
import { useEffect } from "react";

export function useMountEffect(effect: () => undefined | (() => void)) {
	// biome-ignore lint/correctness/useExhaustiveDependencies: intentionally runs once on mount
	useEffect(effect, []);
}

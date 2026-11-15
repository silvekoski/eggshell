// One component per scene id in script.json. A scene id without a component renders a placeholder card.
import type React from "react";
import { S00, S01, S02, S03, S04, S05, S06, S07, S08, S09 } from "./egg";

export const SCENES: Record<string, React.FC<{ dur: number }>> = { s00: S00, s01: S01, s02: S02, s03: S03, s04: S04, s05: S05, s06: S06, s07: S07, s08: S08, s09: S09 };

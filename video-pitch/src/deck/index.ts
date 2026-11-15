// A separate entry for the deck: npx remotion render src/deck/index.ts Deck <dir> --sequence --image-format=png
import { registerRoot } from "remotion";
import { DeckRoot } from "./DeckRoot";

registerRoot(DeckRoot);

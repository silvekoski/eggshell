import { Composition } from "remotion";
import { DECK_SLIDES, Deck } from "./Deck";

export const DeckRoot = () => <Composition id="Deck" component={Deck} durationInFrames={DECK_SLIDES} fps={30} width={1920} height={1080} />;

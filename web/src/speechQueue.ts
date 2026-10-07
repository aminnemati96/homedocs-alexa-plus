import { playAudio, stopAudio, synthesize } from "./api";

// A sentence ends at . ! or ? followed by whitespace. Requiring the space keeps
// "$112.40" together; the last sentence is flushed by finish().
const SENTENCE = /^([\s\S]*?[.!?])\s+/;

/**
 * Speaks a streamed answer sentence by sentence: each sentence is sent to Polly
 * as soon as it is complete, while Claude is still writing the next one, and the
 * clips play back in order. This starts the voice well before the full answer exists.
 */
export class SpeechQueue {
  private buffer = "";
  private chain: Promise<void> = Promise.resolve();
  private stopped = false;
  private onFirstAudio: (() => void) | null;

  constructor(onFirstAudio: () => void) {
    this.onFirstAudio = onFirstAudio;
  }

  push(delta: string): void {
    this.buffer += delta;
    let match: RegExpMatchArray | null;
    while ((match = this.buffer.match(SENTENCE))) {
      this.enqueue(match[1]);
      this.buffer = this.buffer.slice(match[0].length);
    }
  }

  /** Speak whatever is left; resolves when everything has played (or was stopped). */
  finish(): Promise<void> {
    if (this.buffer.trim()) this.enqueue(this.buffer);
    this.buffer = "";
    return this.chain;
  }

  stop(): void {
    this.stopped = true;
    stopAudio();
  }

  private enqueue(sentence: string): void {
    const text = sentence.trim();
    if (!text || this.stopped) return;
    const audio = synthesize(text); // start fetching now, in parallel with playback
    audio.catch(() => {}); // reported when its turn to play comes
    this.chain = this.chain.then(async () => {
      if (this.stopped) return;
      const clip = await audio;
      if (this.stopped) return;
      this.onFirstAudio?.();
      this.onFirstAudio = null;
      await playAudio(clip);
    });
  }
}

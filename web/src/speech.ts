// Browser speech-to-text (Web Speech API). Chrome and Edge support it; Firefox does not.

const Recognition: typeof SpeechRecognition | undefined =
  window.SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition;

export const speechSupported = Recognition !== undefined;

/**
 * Listen for one utterance. onInterim gets partial text while the user speaks.
 * Resolves with the final text ("" if nothing was heard). Returns a stop function too.
 */
export function listenOnce(onInterim: (text: string) => void): {
  result: Promise<string>;
  stop: () => void;
} {
  if (!Recognition) {
    return { result: Promise.reject(new Error("Speech recognition is not supported")), stop: () => {} };
  }
  const recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;

  const result = new Promise<string>((resolve, reject) => {
    let finalText = "";
    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const piece = event.results[i];
        if (piece.isFinal) finalText += piece[0].transcript;
        else interim += piece[0].transcript;
      }
      onInterim((finalText + interim).trim());
    };
    recognition.onerror = (event) => {
      if (event.error === "no-speech" || event.error === "aborted") resolve("");
      else reject(new Error(`Speech recognition error: ${event.error}`));
    };
    recognition.onend = () => resolve(finalText.trim());
  });

  recognition.start();
  return { result, stop: () => recognition.stop() };
}

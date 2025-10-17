//Set the text content of a document element to a given string and then make it fade out after
//a while.
//Parameters:
// - element: The document element to animate.
// - text: The text to display.
// - solid_duration: How long to wait before fading out.
// - fade_duration: How long the fade out will last.
export function set_text_and_fadeout(element, text, solid_duration, fade_duration) {
  const animation_delay = 50;

  element.textContent = text;
  element.style.opacity = 1;

  setTimeout(() => {
    let elapsed_time = 0;
    const interval = setInterval(() => {
      elapsed_time += animation_delay;
      element.style.opacity = (fade_duration - elapsed_time) / fade_duration;
      if (elapsed_time >= fade_duration) {
        clearInterval(interval);
      }
    }, animation_delay);
  }, solid_duration);
}

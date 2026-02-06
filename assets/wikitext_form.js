import { set_text_and_fadeout } from './simple_effects.js';

//Register a custom submit handler for wikitext forms.
//Parameters:
// - form: The main form element to be handled. It must contain a custom "data-method" property that
//   specifies the HTTP method that will be used to send the form.
// - response_msg: An HTML element used for displaying the result of the form send process.
export function register_submit_listener(form, response_msg) {
  form.addEventListener('submit', async (event) => {
    //Disallow default handling of the form
    event.preventDefault();

    //Send the form data using the form action URL and method, then read the response body
    const response = await fetch(form.action, {
      method: form.dataset.method,
      body: new FormData(form)
    });
    const response_text = await response.text();

    if (response.ok) {
      //If all goes well, briefly show a successful operation message
      set_text_and_fadeout(response_msg, 'Review saved!', 1000, 500);
    }
    else {
      //If something goes wrong, use the server response body to show the error message
      response_msg.innerHTML = response_text;
      response_msg.style.opacity = 1;
    }
  });
}

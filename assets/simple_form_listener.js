import { set_text_and_fadeout } from './simple_effects.js';

//Register a custom submit handler for simple HTML forms.
//Parameters:
// - form: The main form element to be handled. It must contain a custom "data-method" property that
//   specifies the HTTP method that will be used to send the form.
// - response_elem: An HTML element used for displaying the result of the form send process. Its
//   text contents will be set to the callback return value if one is provided and it returns any
//   non null/undefined value, otherwise the text contents will be set to the server response body.
//   The 'success' CSS subclass is set upon successful server response, otherwise the 'error' CSS
//   subclass is set instead.
// - fade: Indicates if the response text should be faded out upon a successful request.
// - callback: A callback function that gets called after the form send process is completed.
//Callback parameters:
// - success: A boolean that tells if the request was successful.
// - response_text: The server response string.
//Callback return value: A value (e.g. a string) that is used to update the provided HTML element.
export function register_submit_listener(form, response_elem,
                                         { fade = false, callback = null } = {})
{
  form.addEventListener('submit', async (event) => {
    //Disallow default handling of the form
    event.preventDefault();

    //Send the form data using the form action URL and method, then read the response body
    const response = await fetch(form.action, {
      method: form.dataset.method,
      body: new FormData(form)
    });
    const response_text = await response.text();

    //Invoke the callback if needed
    let response_message;
    if (callback) {
      const callback_result = callback(response.ok, response_text);
      response_message = callback_result != null? callback_result: response_text;
    }
    else {
      response_message = response_text;
    }

    //Set the corresponding CSS subclass according to the outcome
    if (response.ok) {
      response_elem.classList.remove('error');
      response_elem.classList.add('success');
    }
    else {
      response_elem.classList.remove('success');
      response_elem.classList.add('error');
    }

    //If fade is requested and the request is successful, briefly show the server response body,
    //otherwise show the response body statically
    if (fade && response.ok) {
      set_text_and_fadeout(response_elem, response_message, 1000, 500);
    }
    else {
      response_elem.textContent = response_message;
      response_elem.style.opacity = 1;
    }
  });
}

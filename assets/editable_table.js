//Register a click event handler for the edit button in a table row, which allows to switch the
//visibility of the value labels for the corresponding form elements.
//Parameters:
// - row: The row number of the table. Document elements will be referenced by this.
// - col_total: The total amount of columns in every row. Also used to reference document elements.
export function register_edit_listener(row, col_total) {
  //Get a reference to the edit and update buttons.
  const edit = document.getElementById(`row_${row}_edit_button`);
  const update = document.getElementById(`row_${row}_update_button`);

  edit.addEventListener('click', () => {
    //Exchange the visibility of the edit and update buttons
    edit.hidden = true;
    update.hidden = false;

    //Exchange the visibility between value labels and form elements for every row
    for (let i = 0; i < col_total; i++) {
      //Get a reference to the value label and form element, if available
      const label = document.getElementById(`value_label_${row}_${i}`);
      const form_element = document.getElementById(`form_element_${row}_${i}`);

      //If there's both a value label and a form element (meaning the field can be updated),
      //exchange their visibility
      if (form_element && label) {
        form_element.hidden = false;
        label.hidden = true;
      }
    }
  });
}

//Register a custom submit handler for table forms.
//Parameters:
// - form: The main form element to be handled. It must contain one or more submitters (e.g. submit
//   buttons) that specify the "action" URL property and a custom "data-method" property that
//   specifies the HTTP method that will be used to send the form.
export function register_submit_listener(form, confirm_message) {
  form.addEventListener('submit', async (event) => {
    //Disallow default handling of the form
    event.preventDefault();

    //Show a confirmation message if provided, then abort if the user cancels
    if ('warning' in event.submitter.dataset) {
      const message = JSON.parse(event.submitter.dataset.warning);
      if (message != null && !confirm(message)) {
        return;
      }
    }

    //Form data is handled in a way that deviates from standard form submission (in particular
    //checkboxes are always included regardless of their checked state). Iterate over the form
    //elements and collect the data.
    const form_data = new FormData();
    for (const element of event.target.elements) {
      //Skip elements that have no name or that are disabled
      if (!element.name || element.disabled) {
        continue;
      }

      switch (element.type) {
        case 'text':
          //Always collect basic text input elements
          form_data.append(element.name, element.value);
          break;
        case 'submit':
          //Only collect the submit button that caused the form submission, ignore the rest
          if (element === event.submitter)
            form_data.append(element.name, element.value);
          break;
        case 'checkbox':
          //Collect the checkboxes regardless of their checked state, also ignore their value and
          //always send 1 or 0 instead
          if (element.checked)
            form_data.append(element.name, '1');
          else
            form_data.append(element.name, '0');
          break;
        default:
          throw `Unsupported form element type: ${element.type}`
      }
    }

    //Send the form data using the submitter action URL and method, then read the response body
    const response = await fetch(event.submitter.formAction,
                                 { method: event.submitter.dataset.method,
                                   body: form_data });
    const response_text = await response.text();

    if (response.ok) {
      //If all goes well, reset the form to clear potential leftover input data and refresh the view
      form.reset();
      window.location.reload();
    }
    else {
      //If something goes wrong, check the server response body and show an error message
      const response_msg = document.getElementById('response_msg');

      const error_params = response_text.split(',');
      switch (error_params[0]) {
        case 'MISSING_FIELD':
          response_msg.style.color = 'red';
          response_msg.textContent = `The field "${error_params[1]}" is missing`;
          break;
        case 'FIELD_CONFLICT':
          response_msg.style.color = 'red';
          response_msg.textContent = `There's a conflict for the field "${error_params[1]}"`;
          break;
        default:
          //The response could not be characterized, show it verbatim instead
          response_msg.innerHTML = response_text;
          break;
      }
    }
  });
}

import { do_api_query } from './mediawiki_api_client.js';
import { format_local_datetime, format_storage_units } from './format_utils.js';
import { set_text_and_fadeout } from './simple_effects.js';
import { color_map } from './math_utils.js';

//Functions for querying and processing data from the wiki
//--------------------------------------------------------------------------------------------------

//Query the wiki for information on a non-image file
async function query_file_info(api_url, image_title) {
  //Query parameters for obtaining file information
  const params = new URLSearchParams({
    'action': 'query',
    'titles': image_title,
    'prop': 'imageinfo',
    'iiprop': 'timestamp|url|size',
    'iilimit': 'max',
  });

  //Perform the API query
  const api_results = await do_api_query(api_url, params);

  //Extract the image information field from the response
  const imageinfo = Object.values(api_results.query.pages)[0].imageinfo;

  //Prepare the base results structure
  const results = {
    descriptionurl: imageinfo[0].descriptionurl,
    revisions: []
  };

  //Extract relevant revision information
  for (const img_info of imageinfo) {
    results.revisions.push({
      size: img_info.size,
      dimensions: 'unknown',
      timestamp: img_info.timestamp,
    });
  }

  return results;
}

//Query the wiki for information on a file, assuming it's an image
async function query_image_info(api_url, image_title) {
  //Query parameters for obtaining image information
  const params = new URLSearchParams({
    'action': 'query',
    'titles': image_title,
    'prop': 'imageinfo',
    'iiprop': 'timestamp|url|size',
    'iilimit': 'max',
    'iiurlwidth': 120,
    'iiurlheight': 120
  });

  //Perform the API query
  const api_results = await do_api_query(api_url, params);

  if ('error' in api_results) {
    if ('code' in api_results.error && api_results.error.code === 'urlparamnormal') {
      //A parameter normalization error most likely means that this file is not an image and
      //therefore a thumbnail could not be generated. Repeat the query in a simplified way.
      return await query_file_info(api_url, image_title);
    }
    else {
      throw 'Unable to obtain image information';
    }
  }

  //Extract the image information field from the response
  const imageinfo = Object.values(api_results.query.pages)[0].imageinfo;

  //Prepare the base results structure
  const results = {
    descriptionurl: imageinfo[0].descriptionurl,
    revisions: []
  };

  //Extract relevant revision information
  for (const img_info of imageinfo) {
    results.revisions.push({
      size: img_info.size,
      dimensions: (img_info.width > 0 && img_info.height > 0)?
                  img_info.width + ' x ' + img_info.height:
                  'unknown',
      timestamp: img_info.timestamp,
      url: img_info.url,
      thumburl: img_info.thumburl,
    });
  }

  return results;
}

//Query the wiki for information on multiple files
async function query_multiple_images(api_url, image_titles) {
  //Query parameters for obtaining image information
  const params = new URLSearchParams({
    'action': 'query',
    'titles': image_titles.join('|'),
    'prop': 'imageinfo',
    'iiprop': 'timestamp|url',
    'iilimit': 'max',
    'iiurlwidth': 120,
    'iiurlheight': 120
  });

  //Perform the API query
  const api_results = await do_api_query(api_url, params);

  //Extract relevant image information
  const image_info = {};
  for (const page of Object.values(api_results.query.pages)) {
    image_info[page.title] = {};

    //Extract relevant revision information
    for (const revision of page.imageinfo) {
      image_info[page.title][revision.timestamp] = {
        'thumburl': revision.thumburl,
        'descriptionurl': revision.descriptionurl,
      };
    }
  }

  return image_info;
}

//Functions for managing and updating DOM elements
//--------------------------------------------------------------------------------------------------

//Updates the display status of elements in the similar image strip and returns their count
function update_similar_images(state, ref_timestamp, enable) {
  if (ref_timestamp in state.similar_img_strip_elements) {
    //Only update if the reference revision is in the similar image strip elements, which means that
    //the similar image data has been loaded
    let modified_element_count = 0;

    for (const strip_element of state.similar_img_strip_elements[ref_timestamp]) {
      if (enable) strip_element.style.display = '';
      else        strip_element.style.display = 'none';
      modified_element_count++;
    }

    return modified_element_count;
  }
  else {
    //The similar image data has not been loaded yet, so the amount of elements that should be
    //modified cannot be determined
    return undefined;
  }
}

//Select an image from the revisions strip and update the DOM accordingly
function select_image(state, new_index = state.selected_image) {
  const current_image = document.getElementById('current_image');
  const revision_strip = document.getElementById('revision_strip');
  const similar_image_strip_label = document.getElementById('similar_image_strip_label');

  //Make sure revisions are loaded before proceeding
  if (new_index in state.revisions) {
    //Set the current image to the selected revision
    current_image.src = state.revisions[new_index].url;

    //Pass the selection status (subclass) to the new selected image
    revision_strip.children[state.selected_image].children[0].classList.remove('selected');
    revision_strip.children[new_index].children[0].classList.add('selected');

    //Update the similar image strip to show images for the now selected revision
    update_similar_images(state, state.revisions[state.selected_image].timestamp, false);
    const similar_image_count = update_similar_images(state, state.revisions[new_index].timestamp,
                                                      true);

    //Update the similar image count
    if (similar_image_count === 0)
      similar_image_strip_label.textContent = 'No similar images';
    else if (similar_image_count === 1)
      similar_image_strip_label.textContent = '1 possibly similar image:';
    else if (Number.isInteger(similar_image_count))
      similar_image_strip_label.textContent = `${similar_image_count} possibly similar images:`;

    state.selected_image = new_index;
  }
}

//Populate a select element with options and preselect a default option if given
//Parameters:
// - select_element: The select element to populate
// - options: An array of ojects, with a "name" field that is used as the text and value of each
//   option and a "description" field that is used as the title (tooltip)
// - preselected_option: One of the following:
//   - null: Specifically require no option to be preselected (always select the guidance option)
//   - empty string: Same as null
//   - undefined: Don't preselect any particular option, but allow to automatically preselect an
//     option if exactly one is given (otherwise select the guidance option)
//   - An string with the text/value of the preselected option
function populate_select_element(select_element, options, preselected_option) {
  //Abort if there are no options
  if (options.length === 0) {
    return;
  }

  //Add a default disabled guidance option
  const default_option = new Option('-- Select an option --', '');
  default_option.disabled = true;
  default_option.hidden = true;
  default_option.selected = preselected_option === null ||
                            preselected_option === '' ||
                            preselected_option === undefined && options.length > 1;
  select_element.add(default_option);

  //Add the given options
  for (const o of options) {
    const option_element = new Option(o.name, o.name);
    option_element.title = o.description;
    option_element.selected = o.name === preselected_option;
    select_element.add(option_element);
  }
}

//Populate or repopulate a select element with the reasons associated to a given action
function refresh_reasons_select_element(reason_select, cleanup_actions, action_name,
                                        preselected_option)
{
  //Start by clearing the reason select element in case it has any registered option
  reason_select.options.length = 0;

  //Locate the matching action descriptor object in the array
  const action = cleanup_actions.find(a => a.name === action_name);

  //If the action name is not valid, return with an unpopulated reason select element
  if (action === undefined)
    return;

  //Repopulate the reason select element with the reasons available for the indicated action, using
  //the provided preselected option
  populate_select_element(reason_select, action.cleanup_reasons, preselected_option);
}

//Initialize all DOM elements in the common options section
export function initialize_common_options(state, cleanup_actions) {
  const common_action = document.getElementById('common_action');
  const common_reason = document.getElementById('common_reason');
  const apply_all = document.getElementById('apply_all');
  const apply_unset = document.getElementById('apply_unset');
  const unset_all = document.getElementById('unset_all');

  //Populate the common action/reason select elements with automatic default values
  populate_select_element(common_action, cleanup_actions, undefined);
  refresh_reasons_select_element(common_reason, cleanup_actions, common_action.value, undefined);

  //Add an event listener that updates the options available in the reason select element whenever
  //an action is chosen
  common_action.addEventListener('change', (event) => {
    refresh_reasons_select_element(common_reason, cleanup_actions, common_action.value, undefined);
  });

  //Add an event listener to the button that applies the selected common action and reason to all
  //revision reviews, overwriting their current selections
  apply_all.addEventListener('click', () => {
    const revision_strip = document.getElementById('revision_strip');
    for (let index = 0; index < state.revisions.length; index++) {
      const action_select = document.getElementById(`action_${index}`);
      const reason_select = document.getElementById(`reason_${index}`);

      action_select.value = common_action.value;
      refresh_reasons_select_element(reason_select, cleanup_actions, common_action.value,
                                     common_reason.value);
    }
  });

  //Add an event listener to the button that applies the selected common action and reason to every
  //revision review that hasn't been filled in yet.
  apply_unset.addEventListener('click', () => {
    for (let index = 0; index < state.revisions.length; index++) {
      const action_select = document.getElementById(`action_${index}`);
      const reason_select = document.getElementById(`reason_${index}`);

      //Fill both the action and reason only if none of them have been set yet
      if (action_select.value === '' && reason_select.value === '') {
        action_select.value = common_action.value;
        refresh_reasons_select_element(reason_select, cleanup_actions, common_action.value,
                                      common_reason.value);
      }
    }
  });

  //Add an event listener to the button that clears every selected action and reason from every
  //revision review
  unset_all.addEventListener('click', () => {
    const revision_strip = document.getElementById('revision_strip');
    for (let index = 0; index < state.revisions.length; index++) {
      const action_select = document.getElementById(`action_${index}`);
      const reason_select = document.getElementById(`reason_${index}`);

      action_select.value = '';
      refresh_reasons_select_element(reason_select, []);
    }
  });
}

//Query the wiki for information about the current image and update the DOM when completed
export async function download_revision_data(api_url, state, image_title, cleanup_actions,
                                             cleanup_proposal)
{
  const wiki_link = document.getElementById('wiki_link');
  const revision_strip = document.getElementById('revision_strip');

  //Query file information first
  const image_info = await query_image_info(api_url, image_title);

  //Set the wiki link URL and get the revisions
  wiki_link.href = image_info.descriptionurl;
  state.revisions = image_info.revisions;

  let min_size = Infinity, max_size = 0;
  for (let index = 0; index < state.revisions.length; index++) {
    //Create a new element in the thumbnail strip
    const rev_strip_element = revision_strip.appendChild(document.createElement('div'));
    rev_strip_element.classList.add('revision');
    rev_strip_element.innerHTML = `
    <div class="revision_thumbnail" id="revision_img_div_${index}">
      <img id="revision_img_${index}">
    </div>
    <div class="revision_form">
      <div>
        <label for="action_${index}"> Action: </label>
        <select id="action_${index}" form="review_form" name="action_${index}" required></select>
      </div>
      <div>
        <label for="reason_${index}"> Reason: </label>
        <select id="reason_${index}" form="review_form" name="reason_${index}" required></select>
      </div>
      <div id="revision_msg_${index}" style="color: red;">
      </div>
    </div>
    <div class="revision_details" id="revision_size_${index}">
      <div> Size: </div>
      <div> ${format_storage_units(state.revisions[index].size)} </div>
    </div>
    <div class="revision_details">
      <div> Dimensions: </div>
      <div> ${state.revisions[index].dimensions} </div>
      <div> Time: </div>
      <div> ${format_local_datetime(state.revisions[index].timestamp)} </div>
    </div>
    `;

    //Set the source to the revision thumbnail
    const img = document.getElementById(`revision_img_${index}`);
    img.src = state.revisions[index].thumburl;

    //Add a click event listener to the selectable thumbnail container
    const img_container = document.getElementById(`revision_img_div_${index}`);
    img_container.addEventListener('click', () => { select_image(state, index); });

    //The action and reason select elements will be populated with their registered information next
    const action_select = document.getElementById(`action_${index}`);
    const reason_select = document.getElementById(`reason_${index}`);
    const msg_div = document.getElementById(`revision_msg_${index}`);
    const timestamp = state.revisions[index].timestamp;

    //Attempt to load the stored review data, if available
    if (timestamp in cleanup_proposal) {
      //There's a review stored for this revision, get the currently stored action and reason
      const stored_action = cleanup_proposal[timestamp].cleanup_action_name;
      const stored_reason = cleanup_proposal[timestamp].cleanup_reason_name;

      if (cleanup_actions.some(a => a.name === stored_action)) {
        //The stored action is still valid, populate the action select element with a default
        populate_select_element(action_select, cleanup_actions, stored_action);

        //Get the reasons associated to the currently stored action
        const cleanup_reasons = cleanup_actions.find(a => a.name === stored_action).cleanup_reasons;

        if (cleanup_reasons.some(r => r.name === stored_reason)) {
          //The stored reason is still valid, populate the reason select element with a default
          populate_select_element(reason_select, cleanup_reasons, stored_reason);
        }
        else {
          //The stored reason is now invalid, populate the reason select element with no default and
          //warn about the situation
          populate_select_element(reason_select, cleanup_reasons, null);
          msg_div.textContent = `Previously selected reason is now invalid: ${stored_reason}`;
        }
      }
      else {
        //The stored action is now invalid, populate the action select element with no default and
        //warn about the situation
        populate_select_element(action_select, cleanup_actions, null);
        msg_div.textContent = `Previously selected action is now invalid: ${stored_action}`;
      }
    }
    else {
      //There's no review stored for this revision, populate the action and reason select elements
      //with automatic default values
      populate_select_element(action_select, cleanup_actions, undefined);
      refresh_reasons_select_element(reason_select, cleanup_actions, action_select.value,
                                     undefined);
    }

    //Add an event listener that updates the options available in the reason select element whenever
    //an action is chosen
    action_select.addEventListener('change', (event) => {
      //Clear the error message (if any), then refresh the reason select element with the reasons
      //available for the newly selected action with an automatic default value
      msg_div.textContent = '';
      refresh_reasons_select_element(reason_select, cleanup_actions, action_select.value,
                                     undefined);
    });

    //Add an event listener that clears the the error message (if any) whenever a reason is chosen
    reason_select.addEventListener('change', (event) => {
      msg_div.textContent = '';
    })

    //Keep track of minimum and maximum file sizes
    if (state.revisions[index].size < min_size)
      min_size = state.revisions[index].size;

    if (state.revisions[index].size > max_size)
      max_size = state.revisions[index].size;
  }

  //Color scale applied to revision sizes
  const color_scale = [
    [   0, 255,   0],   //Green
    [ 255, 255,   0],   //Yellow
    [ 255,   0,   0],   //Red
  ];

  //Color the background of the size fields in the revision strip to give a rough visual comparison
  if (min_size != max_size) {
    for (let index = 0; index < state.revisions.length; index++) {
      const size_div = document.getElementById(`revision_size_${index}`);

      //Calculate a color index using a logarithmic scale between the minimum and maximum size
      const continuous_index = Math.log10(state.revisions[index].size / min_size) /
                               Math.log10(max_size / min_size) * (color_scale.length - 1);

      //Map the color and apply
      const color = color_map(color_scale, continuous_index);
      size_div.style.backgroundColor = `rgba(${color[0]}, ${color[1]}, ${color[2]}, 0.5)`;
    }
  }

  select_image(state);  //Refresh the selected image
}

//Query the wiki for information about images similar to the current one and update the DOM when
//completed
export async function download_similar_image_data(api_url, state, similar_images) {
  const similar_img_strip = document.getElementById('similar_img_strip');

  //Retrieve all unique titles from the similar_images object
  const similar_image_titles = [];
  for (const image of Object.values(similar_images)) {
    for (const title in image) {
      if (!similar_image_titles.includes(title)) {
        similar_image_titles.push(title);
      }
    }
  }

  //Avoid querying for information if there's no similar images
  if (similar_image_titles.length === 0)
    return;

  //Query for information on similar images
  const wiki_image_info = await query_multiple_images(api_url, similar_image_titles);

  //Perform a nested iteration over the similar image (si) information object, down to each revision
  const similar_img_elements = {};  //Temporary holder for element references
  for (const ref_timestamp in similar_images) {
    //Prepare an empty array for potential references to similar image strip elements
    state.similar_img_strip_elements[ref_timestamp] = [];
    //Note: a zero length array is valid and used to signal that there are no similar images after
    //downloading image information from the wiki

    for (const [si_title, similar_image_status] of Object.entries(similar_images[ref_timestamp])) {
      //If the wiki didn't return information for the requested image, skip it, as the image
      //could've been recently deleted and there's no point in reporting it anymore
      if (!(si_title in wiki_image_info))
        continue;

      for (const si_timestamp of similar_image_status.revisions) {
        //If the wiki didn't return information for the referenced revision, skip it as well
        if (!(si_timestamp in wiki_image_info[si_title]))
          continue;

        //If the title and timestamp are in the temporary references, simply link the existing DOM
        //element, as more than revision is referencing it
        if (si_title in similar_img_elements && si_timestamp in similar_img_elements[si_title])
        {
          state.similar_img_strip_elements[ref_timestamp].push(
            similar_img_elements[si_title][si_timestamp]);

          continue;
        }

        //Add a new DIV container to the similar image strip, then populate it with details
        //regarding to that particular image. Make it initially invisible until a related revision
        //is selected.
        const container = similar_img_strip.appendChild(document.createElement('div'));
        container.classList.add('similar_image_strip_item');
        container.style.display = 'none';
        container.innerHTML = `
        <div class="similar_image">
          <img src="${wiki_image_info[si_title][si_timestamp].thumburl}">
        </div>
        <div>
        <div class="similar_image_title">
          ${si_title}
        </div>
          <span style="color: ${similar_images[ref_timestamp][si_title].unused? 'red': 'green'};">
            ${similar_images[ref_timestamp][si_title].unused? '&cross;': '&check;'}
          </span>
          <a href="${wiki_image_info[si_title][si_timestamp].descriptionurl}" target="_blank">
            ${similar_images[ref_timestamp][si_title].unused? 'Not in use': 'In use'}
          </a>
        </div>
        <div>
          <span style="color: ${similar_images[ref_timestamp][si_title].reviewed? 'green': 'red'};">
            ${similar_images[ref_timestamp][si_title].reviewed? '&check;': '&cross;'}
          </span>
          <a href="${similar_images[ref_timestamp][si_title].review_url}" target="_blank">
            ${similar_images[ref_timestamp][si_title].reviewed? 'Reviewed': 'Not reviewed'}
          </a>
        </div>
        `;

        //Append the newly created container to the similar image strip elements array, so that it
        //can be referenced when selecting a revision
        state.similar_img_strip_elements[ref_timestamp].push(container);

        //Also add the container to the temporary references, so that it can be reused if referenced
        //by another revision
        if (!(si_title in similar_img_elements))  //Create the object only once
          similar_img_elements[si_title] = {};

        similar_img_elements[si_title][si_timestamp] = container;
      }
    }
  }

  select_image(state);  //Refresh the selected image
}

//Functions for handling form data and submit requests
//--------------------------------------------------------------------------------------------------

//Register a custom submit handler for image reviews.
//Parameters:
// - state: Contains the dynamic state of the web page, particularly the revision information
//   downloaded from the wiki.
export async function register_review_submit_listener(state) {
  const form = document.getElementById('review_form');
  const form_submit_result = document.getElementById('form_submit_result');

  form.addEventListener('submit', async (event) => {
    //This form will be sent with the PUT method, so prevent default handling
    event.preventDefault();

    //Gather the form data as an object before sending
    const form_data = {
      'comments': event.target.elements.comments.value,
      'revisions': {},
    };

    for (let index = 0; index < state.revisions.length; index++) {
      const action_element = event.target.elements[`action_${index}`];
      const reason_element = event.target.elements[`reason_${index}`];
      form_data['revisions'][state.revisions[index].timestamp] = {
        'action': action_element.value,
        'reason': reason_element.value,
      };
    }

    //Send the form data as JSON, then read the response body
    const response = await fetch(event.target.action,
                                 { method: 'PUT',
                                   headers: { 'Content-Type': 'application/json' },
                                   body: JSON.stringify(form_data) });
    const response_text = await response.text();

    if (response.ok) {
      //If all goes well, briefly show a successful operation message
      set_text_and_fadeout(form_submit_result, 'Review saved!', 1000, 500);
    }
    else {
      //If something goes wrong, use the server response body to show the error message
      form_submit_result.innerHTML = response_text;
      form_submit_result.style.opacity = 1;
    }
  });
}

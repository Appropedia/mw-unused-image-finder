import { do_api_query } from './mediawiki_api_client.js';
import { format_local_datetime, format_storage_units } from './format_utils.js';
import { set_text_and_fadeout } from './simple_effects.js';

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
export async function query_image_info(api_url, image_title) {
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
export async function query_multiple_images(api_url, image_titles) {
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

//Updates the display status of items in the similar image strip
function update_similar_images(state, ref_timestamp, enable) {
  //Don't update if the reference revision has no similar images (or have not been loaded yet)
  if (ref_timestamp in state.similar_img_strip_items) {
    for (const strip_item of state.similar_img_strip_items[ref_timestamp]) {
      if (enable) strip_item.style.display = '';
      else        strip_item.style.display = 'none';
    }
  }
}

//Select an image from the revisions strip and update the DOM accordingly
export function select_image(state, new_index = state.selected_image) {
  const current_image = document.getElementById('current_image');
  const revision_size = document.getElementById('revision_size');
  const revision_dimensions = document.getElementById('revision_dimensions');
  const revision_time = document.getElementById('revision_time');
  const revision_strip = document.getElementById('revision_strip');

  //Make sure revisions are loaded before proceeding
  if (new_index in state.revisions) {
    //Set the current image to the selected revision and update revision information
    current_image.src = state.revisions[new_index].url;
    revision_size.textContent = format_storage_units(state.revisions[new_index].size);
    revision_dimensions.textContent = state.revisions[new_index].dimensions;
    revision_time.textContent = format_local_datetime(state.revisions[new_index].timestamp);

    //Pass the selection status (subclass) to the new selected image
    revision_strip.children[state.selected_image].children[0].classList.remove('selected');
    revision_strip.children[new_index].children[0].classList.add('selected');

    //Update the similar image strip to show images for the now selected revision
    update_similar_images(state, state.revisions[state.selected_image].timestamp, false);
    update_similar_images(state, state.revisions[new_index].timestamp, true);

    state.selected_image = new_index;
  }
}

//Populate a select element with options and pre-select a default option if given
//Parameters:
// - select_element: The select element to populate
// - options: An array of ojects, with a "name" field that is used as the text and value of each
//   option and a "description" field that is used as the title (tooltip)
// - selected_option: One of the following:
//   - null: Specifically require no option to be pre-selected (always select the guidance option)
//   - undefined: Don't pre-select any particular option, but allow to automatically pre-select an
//     option if exactly one is given (otherwise select the guidance option)
//   - An string with the text/value of the pre-selected option
function populate_select_element(select_element, options, selected_option) {
  //Abort if there are no options
  if (options.length === 0) {
    return;
  }

  //Add a default disabled guidance option
  const default_option = new Option('-- Select an option --', '');
  default_option.disabled = true;
  default_option.selected = selected_option === null ||
                            selected_option === undefined && options.length > 1;
  select_element.add(default_option);

  //Add the given options
  for (const o of options) {
    const option_element = new Option(o.name, o.name);
    option_element.title = o.description;
    option_element.selected = o.name === selected_option;
    select_element.add(option_element);
  }
}

//Query the wiki for information about the current image and update the DOM when completed
export async function download_revision_data(api_url, state, image_title, cleanup_actions,
                                             review_data)
{
  const wiki_link = document.getElementById('wiki_link');
  const revision_strip = document.getElementById('revision_strip');

  const image_info = await query_image_info(api_url, image_title);

  //Set the wiki link URL and get the revisions
  wiki_link.href = image_info.descriptionurl;
  state.revisions = image_info.revisions;

  for (let index = 0; index < state.revisions.length; index++) {
    //Create a new item in the thumbnail strip
    const rev_strip_item = revision_strip.appendChild(document.createElement('div'));
    rev_strip_item.classList.add('revision');
    rev_strip_item.innerHTML = `
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
    if (timestamp in review_data) {
      //There's a review stored for this revision, get the currently stored action and reason
      const stored_action = review_data[timestamp].cleanup_action_name;
      const stored_reason = review_data[timestamp].cleanup_reason_name;

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
      //There's no review stored for this revision, populate the action select element with an
      //automatic default value
      populate_select_element(action_select, cleanup_actions, undefined);

      //If an automatic default was set, populate the reason select element with an automatic
      //default value as well
      const pre_selected_action = cleanup_actions.find(a => a.name === action_select.value);

      if (pre_selected_action !== undefined) {
        populate_select_element(reason_select, pre_selected_action.cleanup_reasons, undefined);
      }
    }

    //Add an event listener that updates the options available in the reason select element whenever
    //an action is chosen
    action_select.addEventListener('change', (event) => {
      //Get the cleanup reasons for the newly selected action
      const cleanup_reasons =
      cleanup_actions.find(a => a.name === action_select.value).cleanup_reasons;

      //Clear the error message (if any), then clear and repopulate the reason select element with
      //the reasons available for the newly selected action with an automatic default value
      msg_div.textContent = '';
      reason_select.options.length = 0;
      populate_select_element(reason_select, cleanup_reasons, undefined);
    });

    //Add an event listener that clears the the error message (if any) whenever a reason is chosen
    reason_select.addEventListener('change', (event) => {
      msg_div.textContent = '';
    })
  }

  select_image(state);  //Refresh the selected image
}

//Check whether a revision is defined in the similar images (si) object
function revision_in_similar_images(similar_images, ref_timestamp, si_title, si_timestamp) {
  return si_title in similar_images[ref_timestamp] &&
  similar_images[ref_timestamp][si_title].revisions.includes(si_timestamp);
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
  const similar_image_info = await query_multiple_images(api_url, similar_image_titles);

  //Iterate over the similar image (si) information provided by the wiki
  for (const si_title in similar_image_info) {
    for (const si_timestamp in similar_image_info[si_title]) {
      //Cross the data provided by the wiki against the data provided by the application
      //server. If both provide matching information about an specific revision, mark it as
      //referenced.
      let revision_referenced = false;
      for (const ref_timestamp in similar_images) {
        if (revision_in_similar_images(similar_images, ref_timestamp, si_title, si_timestamp))
        {
          revision_referenced = true;
          break;
        }
      }

      if (revision_referenced) {
        //Add a new thumbnail to the similar image strip using information provided by the
        //wiki. Make it initially invisible until a related revision is selected.
        const img_container = similar_img_strip.appendChild(document.createElement('div'));
        img_container.classList.add('similar_image');
        img_container.style.display = 'none';

        const anchor = img_container.appendChild(document.createElement('a'));
        anchor.href = similar_image_info[si_title][si_timestamp].descriptionurl;
        anchor.target = '_blank';

        const img = anchor.appendChild(document.createElement('img'));
        img.src = similar_image_info[si_title][si_timestamp].thumburl;

        //Cross the data again. For each revision that is referenced by both sides, add a
        //reference of the newly created item to the similar_img_strip_items object.
        for (const ref_timestamp in similar_images) {
          if (!revision_in_similar_images(similar_images, ref_timestamp, si_title, si_timestamp))
            continue;

          //Create the array for the reference timestamp only once
          if (!(ref_timestamp in state.similar_img_strip_items))
            state.similar_img_strip_items[ref_timestamp] = [];

          state.similar_img_strip_items[ref_timestamp].push(img_container);
        }
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

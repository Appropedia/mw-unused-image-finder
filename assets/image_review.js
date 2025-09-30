import { do_api_query } from './mediawiki_api_client.js';

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

export async function query_similar_images(api_url, image_titles) {
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

  //Extract relevant page information
  const similar_images = {};
  for (const page of Object.values(api_results.query.pages)) {
    //Extract relevant revision information
    similar_images[page.title] = {};
    for (const revision of page.imageinfo) {
      similar_images[page.title][revision.timestamp] = {
        'thumburl': revision.thumburl,
        'descriptionurl': revision.descriptionurl,
      };
    }
  }

  return similar_images;
}

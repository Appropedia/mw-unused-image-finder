import { do_api_query } from '../mediawiki_api_client.js';

//Format an ISO timestamp as a local datetime
export function format_local_datetime(iso_datetime) {
  const date = new Date(iso_datetime);
  return date.toLocaleString();
}

//
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

  //Extract the image information field from the response
  const imageinfo = Object.values(api_results.query.pages)[0].imageinfo;

  //Extract relevant fields, if available
  const results = {
    descriptionurl: imageinfo[0].descriptionurl,
    revisions: []
  };

  for (const info of imageinfo) {
    const rev_info = {
      timestamp: info.timestamp,
      thumburl: info.thumburl
    };
    if (info.width > 0 && info.height > 0) {
      rev_info.width = info.width;
      rev_info.height = info.height;
    }
    results.revisions.push(rev_info);
  }

  // console.log(JSON.stringify(api_results, null, 2));
  // console.log(results);

  return results;
}

//
export async function query_similar_image_info(api_url, image_titles) {
  //Query parameters for obtaining image information
  const params = new URLSearchParams({
    'action': 'query',
    'titles': image_titles,
    'prop': 'imageinfo',
    'iiprop': 'timestamp|url',
    'iilimit': 'max',
    'iiurlwidth': 120,
    'iiurlheight': 120
  });

  //Perform the API query
  const api_results = await do_api_query(api_url, params);

  //Extract the image information field from the response
  const imageinfo = Object.values(api_results.query.pages)[0].imageinfo;

  const results = []
  for (const info of imageinfo) {
    results.push({
      thumburl: info.thumburl,
      timestamp: info.timestamp
    })
  }

  // console.log(results);

  return results;
}

//Perform a query to a mediawiki server.
//Parameters:
// - api_url: Where to send the request to.
// - params: Query parameters.
export async function do_api_query(api_url, params) {
  params.append('format', 'json');

  const response = await fetch(api_url + '?' + params.toString())

  if (!response.ok) {
    throw new Error(`API HTTP response status code ${response.status}`);
  }

  return await response.json();
}

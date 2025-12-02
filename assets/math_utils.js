//Returns an RGB color array containing an interpolated color from a given color scale
//Parameters:
// - color_scale: An array of RGB color arrays, with each color array containing the color
//   components in the scale from 0 to 255. The minimum workable length is 1 color.
// - continous_index: A floating point number between 0 and N-1, where N is the total amount of
//   colors in the color scale. Represents a continuous position for which the interpolated color is
//   calculated. Values outside the color scale range are clipped to the closest element.
export function color_map(color_scale, continous_index) {
  //Make sure a workable length is given
  if (color_scale.length < 1)
    return undefined;

  //Clip to low and high values
  if (continous_index <= 0)
    return color_scale[0];

  if (continous_index >= color_scale.length - 1)
    return color_scale.at(-1);

  //Get the indexes of the neighboring colors in the scale
  const lo_idx = Math.floor(continous_index);
  const hi_idx = Math.ceil(continous_index);

  //Get the neighboring colors values in the scale
  const lo_col = color_scale[lo_idx];
  const hi_col = color_scale[hi_idx];

  //Perform linear interpolation on each color component
  const result = [];
  for (let i = 0; i < 3; i++) {
    result.push(lo_col[i] + (hi_col[i] - lo_col[i]) * (continous_index - lo_idx));
  }
  //Note: In the case of lo_idx == hi_idx (e.g. an integer continous_index was given) and/or
  //lo_col == hi_col (e.g. continuous identical color components) the calculation can go normally as
  //index ranges between consecutive colors are already normalized (have a difference of exactly
  //one) therefore no division by zero can occur as dividing isn't needed.

  return result;
}

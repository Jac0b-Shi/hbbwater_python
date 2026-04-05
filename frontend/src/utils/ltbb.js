/**
 * LTTB (Largest Triangle Three Buckets) 降采样算法
 * 用于优化大数据集的图表显示性能
 * 
 * @param {Array} data - 原始数据数组，每项包含 timestamp 和 value
 * @param {Number} threshold - 目标数据点数量
 * @returns {Array} 降采样后的数据
 */
export function lttb(data, threshold = 1000) {
  if (data.length <= threshold || threshold === 0) {
    return data
  }

  const sampled = []
  let sampledIndex = 0

  // Bucket size
  const every = (data.length - 2) / (threshold - 2)

  let a = 0 // Initially a is the first point
  let maxAreaPoint
  let maxArea
  let area

  sampled[sampledIndex++] = data[a] // Add the first point

  for (let i = 0; i < threshold - 2; i++) {
    // Calculate point average for next bucket
    let avgX = 0
    let avgY = 0
    let avgRangeStart = Math.floor((i + 1) * every) + 1
    let avgRangeEnd = Math.floor((i + 2) * every) + 1
    avgRangeEnd = avgRangeEnd < data.length ? avgRangeEnd : data.length

    const avgRangeLength = avgRangeEnd - avgRangeStart

    for (; avgRangeStart < avgRangeEnd; avgRangeStart++) {
      avgX += data[avgRangeStart].timestamp
      avgY += data[avgRangeStart].value
    }
    avgX /= avgRangeLength
    avgY /= avgRangeLength

    // Get the range for this bucket
    let rangeOffs = Math.floor((i + 0) * every) + 1
    let rangeTo = Math.floor((i + 1) * every) + 1

    // Point a
    const pointAX = data[a].timestamp
    const pointAY = data[a].value

    maxArea = -1

    for (; rangeOffs < rangeTo; rangeOffs++) {
      // Calculate triangle area over three buckets
      area = Math.abs(
        (pointAX - avgX) * (data[rangeOffs].value - pointAY) -
        (pointAX - data[rangeOffs].timestamp) * (avgY - pointAY)
      )

      if (area > maxArea) {
        maxArea = area
        maxAreaPoint = data[rangeOffs]
        a = rangeOffs // Next a is this b
      }
    }

    sampled[sampledIndex++] = maxAreaPoint
  }

  sampled[sampledIndex++] = data[data.length - 1] // Add the last point

  return sampled
}

/**
 * 简单的数据降采样
 * @param {Array} data - 原始数据
 * @param {Number} threshold - 目标数量
 * @returns {Array}
 */
export function simpleDownsample(data, threshold = 1000) {
  if (data.length <= threshold) return data
  
  const sampled = []
  const every = Math.floor(data.length / threshold)
  
  for (let i = 0; i < data.length; i += every) {
    sampled.push(data[i])
  }
  
  // Always include last point
  if (sampled[sampled.length - 1] !== data[data.length - 1]) {
    sampled.push(data[data.length - 1])
  }
  
  return sampled
}

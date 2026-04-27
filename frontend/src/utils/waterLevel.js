function toFiniteNumber(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function getRelativeWaterLevel(sensor, measurementValue) {
  const baseline = toFiniteNumber(sensor?.water_level_baseline)
  const measurement = toFiniteNumber(measurementValue)

  if (baseline === null || measurement === null) {
    return null
  }

  return baseline - measurement
}

export function getUltrasonicMetric(sensor, measurementValue) {
  const measurement = toFiniteNumber(measurementValue)
  const relativeWaterLevel = getRelativeWaterLevel(sensor, measurementValue)

  if (relativeWaterLevel !== null) {
    return {
      mode: 'relative',
      label: '相对水位',
      value: relativeWaterLevel,
      unit: 'cm',
    }
  }

  if (measurement !== null) {
    return {
      mode: 'distance',
      label: '实时测距',
      value: measurement,
      unit: 'cm',
    }
  }

  return {
    mode: 'empty',
    label: '暂无数据',
    value: null,
    unit: 'cm',
  }
}

export function formatMetricValue(value, digits = 1) {
  const numericValue = toFiniteNumber(value)
  if (numericValue === null) {
    return '--'
  }

  return numericValue.toFixed(digits)
}

export function hasStoredMapPosition(sensor) {
  return toFiniteNumber(sensor?.map_x) !== null && toFiniteNumber(sensor?.map_y) !== null
}

export function clampPercent(value, min = 2, max = 98) {
  return Math.min(Math.max(value, min), max)
}

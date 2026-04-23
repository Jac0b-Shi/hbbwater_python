const encoder = new TextEncoder()

export const PASSWORD_MIN_LENGTH = 8
export const BCRYPT_PASSWORD_MAX_BYTES = 72
export const PASSWORD_TOO_LONG_MESSAGE = `密码不能超过 ${BCRYPT_PASSWORD_MAX_BYTES} 字节，中文和特殊字符会占用更多字节`

export function getPasswordByteLength(password = '') {
  return encoder.encode(String(password || '')).length
}

export function validatePassword(password, {
  required = true,
  requiredMessage = '请输入密码',
  minimumMessage = `密码长度不能少于 ${PASSWORD_MIN_LENGTH} 位`
} = {}) {
  const value = String(password || '')

  if (!value) {
    return required ? requiredMessage : null
  }

  if (value.length < PASSWORD_MIN_LENGTH) {
    return minimumMessage
  }

  if (getPasswordByteLength(value) > BCRYPT_PASSWORD_MAX_BYTES) {
    return PASSWORD_TOO_LONG_MESSAGE
  }

  return null
}

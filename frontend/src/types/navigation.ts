export interface MenuItem {
  label: string
  icon: string
  to?: string
  active: boolean
  action?: boolean
  id?: string
  bottomSection?: boolean
}

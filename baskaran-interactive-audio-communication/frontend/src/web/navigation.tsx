import { useMemo, type ComponentProps } from 'react'
import { Link as BrowserLink, useNavigate } from 'react-router-dom'

type LinkProps = Omit<ComponentProps<typeof BrowserLink>, 'to'> & { href: string }
export default function Link({ href, ...props }: LinkProps) {
  return <BrowserLink to={href} {...props} />
}

export function useRouter() {
  const navigate = useNavigate()
  return useMemo(() => ({
    push: (href: string) => navigate(href),
    replace: (href: string) => navigate(href, { replace: true }),
    back: () => navigate(-1),
  }), [navigate])
}

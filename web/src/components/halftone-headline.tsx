import HalftoneWordmarkFooter from "@/components/ui/halftone-wordmark-footer";
import { usePrefersReducedMotion } from "@/lib/reduced-motion";

/**
 * The landing hero (US4.2): Nico's pasted halftone component spelling `gsm8k`, without its
 * demo text, link columns or back-to-top. The word is a real, visually hidden `h1`; the
 * component (canvas and its own screen-reader copy of the word) is hidden from assistive
 * technology so the word is heard once. Under reduced motion the dots stay still and the
 * pointer and click do nothing (AC4.2.4); the component is remounted so it re-reads the setting.
 */
export function HalftoneHeadline() {
  const reduced = usePrefersReducedMotion();
  return (
    <section data-motion={reduced ? "still" : "live"} className="relative w-full">
      <h1 className="sr-only">gsm8k</h1>
      <div aria-hidden="true" className="w-full">
        <HalftoneWordmarkFooter
          key={reduced ? "still" : "live"}
          wordmark="gsm8k"
          preset="night"
          label=""
          meta=""
          columns={[]}
          backToTop={false}
          crop={0}
          interactive={!reduced}
          height="40vh"
        />
      </div>
    </section>
  );
}

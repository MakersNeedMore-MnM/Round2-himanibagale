import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Problem from "@/components/Problem";
import MasterySection from "@/components/MasterySection";
import FeaturesSection from "@/components/FeaturesSection";
import DashboardPreview from "@/components/DashboardPreview";
import Modes from "@/components/Modes";
import GetStarted from "@/components/GetStarted";
import Contribute from "@/components/Contribute";
import Footer from "@/components/Footer";

export default function Page() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Problem />
        <MasterySection />
        <FeaturesSection />
        <Modes />
        <DashboardPreview />
        <GetStarted />
        <Contribute />
      </main>
      <Footer />
    </>
  );
}

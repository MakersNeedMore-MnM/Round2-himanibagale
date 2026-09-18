import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Problem from "@/components/Problem";
import HowItWorks from "@/components/HowItWorks";
import Demo from "@/components/Demo";
import DashboardPreview from "@/components/DashboardPreview";
import Modes from "@/components/Modes";
import GetStarted from "@/components/GetStarted";
import Footer from "@/components/Footer";

export default function Page() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Problem />
        <HowItWorks />
        <Demo />
        <DashboardPreview />
        <Modes />
        <GetStarted />
      </main>
      <Footer />
    </>
  );
}

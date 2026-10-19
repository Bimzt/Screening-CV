import ceoStaff from "@/profiles/examples/ceo_staff.json";
import hrta from "@/profiles/examples/hrta.json";
import hrod from "@/profiles/examples/hrod.json";
import dataAnalyst from "@/profiles/examples/data_analyst.json";
import businessDevelopment from "@/profiles/examples/business_development.json";
import eventManagement from "@/profiles/examples/event_management.json";
import customerServices from "@/profiles/examples/customer_service.json";
import contentCreator from "@/profiles/examples/content_creator.json";
import graphicDesign from "@/profiles/examples/graphic_design.json";
import socialMediaStrategist from "@/profiles/examples/social_media_strategist.json";
import { JobProfile } from "./types";

export const DEFAULT_PROFILES_VERSION = "2026-10-19-v2";

export const DEFAULT_EXAMPLE_PROFILES: JobProfile[] = [
  ceoStaff as unknown as JobProfile,
  hrta as unknown as JobProfile,
  hrod as unknown as JobProfile,
  dataAnalyst as unknown as JobProfile,
  businessDevelopment as unknown as JobProfile,
  eventManagement as unknown as JobProfile,
  customerServices as unknown as JobProfile,
  contentCreator as unknown as JobProfile,
  graphicDesign as unknown as JobProfile,
  socialMediaStrategist as unknown as JobProfile,
];

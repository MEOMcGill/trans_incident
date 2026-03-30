## ============================================================================
## Trans / Non-binary comfort expressing political views analysis
## ============================================================================

library(dplyr)
library(tidyr)
library(ggplot2)
library(stringr)

# Source utilities
source("C:/Users/math_/.claude/skills/survey-search/scripts/survey_utils.R")
source("C:/Users/math_/Dropbox/PC/Documents/GitHub/ai_interns/templates/meo_theme.R")

# ── 1. Load and clean ────────────────────────────────────────────────────────

catalogue <- load_catalogue()
data <- read.csv("harmonized_data.csv", fileEncoding = "UTF-8-BOM")
cat("Raw rows:", nrow(data), "\n")

data <- clean_survey_data(data, catalogue)
data <- weight_survey_data(data, catalogue, method = "rake")

write.csv(data, "harmonized_data.csv", row.names = FALSE)

# ── 2. Recode variables ─────────────────────────────────────────────────────

# Harmonize pol_speech scales: codes 1,3,4,5,6 → 1,2,3,4,5
# The general items use codes 1,3,4,5,6; Kirk items use 1,2,3,4,5
# Remap general items to 1-5 scale
recode_comfort <- function(x, is_kirk = FALSE) {
  x <- as.numeric(x)
  if (is_kirk) return(x)  # Already 1-5
  dplyr::case_when(
    x == 1 ~ 1,  # Not at all comfortable
    x == 3 ~ 2,  # Not very comfortable (was code 3, no code 2 in original)
    x == 4 ~ 3,  # Somewhat comfortable
    x == 5 ~ 4,  # Comfortable
    x == 6 ~ 5,  # Very comfortable
    TRUE ~ NA_real_
  )
}

data <- data %>%
  mutate(
    pol_speech_1_r = recode_comfort(pol_speech_1),
    pol_speech_2_r = recode_comfort(pol_speech_2),
    pol_speech_3_r = recode_comfort(pol_speech_3),
    chilled_kirk_1_r = recode_comfort(chilled_kirk_1, is_kirk = TRUE),
    chilled_kirk_2_r = recode_comfort(chilled_kirk_2, is_kirk = TRUE),
    chilled_kirk_3_r = recode_comfort(chilled_kirk_3, is_kirk = TRUE)
  )

# Gender identity variable
# gender1: 1=Man, 2=Woman, 5=Another way, 6=Non-binary, 7=DK
# gender (Federal Post-Election): same coding via catalogue
# gender2: 1=Yes trans, 2=No, 3=DK
data <- data %>%
  mutate(
    gender1_num = as.numeric(gender1),
    # Coalesce gender1 and gender columns
    gender_identity = coalesce(gender1_num, as.numeric(gender)),
    gender_group = case_when(
      gender_identity == 1 ~ "Man",
      gender_identity == 2 ~ "Woman",
      gender_identity %in% c(5, 6) ~ "Non-binary / Other",
      gender_identity == 7 ~ NA_character_,  # DK — exclude
      TRUE ~ NA_character_
    ),
    is_trans = case_when(
      as.numeric(gender2) == 1 ~ "Transgender",
      as.numeric(gender2) == 2 ~ "Not transgender",
      TRUE ~ NA_character_
    ),
    # Combined IV: non-cis group
    gender_minority = case_when(
      gender_group == "Non-binary / Other" | is_trans == "Transgender" ~ "Trans / Non-binary",
      gender_group %in% c("Man", "Woman") & (is_trans == "Not transgender" | is.na(is_trans)) ~ "Cisgender",
      TRUE ~ NA_character_
    )
  )

cat("\nGender group distribution:\n")
data %>% filter(!is.na(gender_group)) %>% count(gender_group) %>% print()
cat("\nTransgender distribution:\n")
data %>% filter(!is.na(is_trans)) %>% count(is_trans) %>% print()
cat("\nGender minority distribution:\n")
data %>% filter(!is.na(gender_minority)) %>% count(gender_minority) %>% print()

# ── 3. Pre/post Kirk assassination (Sept 10, 2025) ──────────────────────────

data <- data %>%
  mutate(
    end_date = as.Date(EndDate),
    period = case_when(
      end_date < as.Date("2025-09-10") ~ "Pre-Kirk",
      end_date >= as.Date("2025-09-10") ~ "Post-Kirk",
      TRUE ~ NA_character_
    )
  )

cat("\nPeriod distribution:\n")
data %>% filter(!is.na(period)) %>% count(period) %>% print()

# ── 4. Analysis: Comfort by gender minority status ──────────────────────────

# Reshape to long for the 3 comfort items
comfort_long <- data %>%
  filter(!is.na(gender_minority)) %>%
  select(ResponseId, survey_name, survey_date, wt, gender_minority, period,
         pol_speech_1_r, pol_speech_2_r, pol_speech_3_r) %>%
  pivot_longer(
    cols = starts_with("pol_speech_"),
    names_to = "item",
    values_to = "comfort"
  ) %>%
  filter(!is.na(comfort)) %>%
  mutate(
    item_label = case_when(
      item == "pol_speech_1_r" ~ "Express political\nopinions online",
      item == "pol_speech_2_r" ~ "Respond to posts\nyou disagree with",
      item == "pol_speech_3_r" ~ "Express opinions\nat work/school"
    )
  )

# Weighted means by group and period
means_by_group_period <- comfort_long %>%
  group_by(gender_minority, period, item_label) %>%
  summarise(
    wtd_mean = weighted.mean(comfort, wt, na.rm = TRUE),
    n = n(),
    se = sqrt(sum(wt^2 * (comfort - weighted.mean(comfort, wt))^2) / sum(wt)^2),
    .groups = "drop"
  ) %>%
  mutate(
    ci_lo = wtd_mean - 1.96 * se,
    ci_hi = wtd_mean + 1.96 * se
  )

cat("\n\n== Comfort by Gender Minority Status and Period ==\n")
means_by_group_period %>%
  arrange(item_label, gender_minority, period) %>%
  print(n = 30)

# ── 5. Figure 1: Dot plot — comfort by gender identity × pre/post Kirk ──────

p1 <- ggplot(means_by_group_period,
             aes(x = wtd_mean, y = item_label, color = gender_minority,
                 shape = period)) +
  geom_pointrange(aes(xmin = ci_lo, xmax = ci_hi),
                  position = position_dodge(width = 0.5), size = 0.6) +
  scale_x_continuous(
    limits = c(1, 5),
    breaks = 1:5,
    labels = c("Not at all\ncomfortable", "Not very", "Somewhat", "Comfortable", "Very\ncomfortable")
  ) +
  scale_color_manual(values = c("Cisgender" = "#434E7C", "Trans / Non-binary" = "#FF8200")) +
  labs(
    title = "Comfort Expressing Political Views Online",
    subtitle = "By gender identity, pre- and post-Charlie Kirk assassination (Sept 10, 2025)",
    x = NULL, y = NULL,
    caption = sprintf("N = %s respondents across %d surveys (July 2024 – Feb 2026). Weighted estimates with 95%% CIs.",
                      format(nrow(comfort_long %>% distinct(ResponseId)), big.mark = ","),
                      length(unique(comfort_long$survey_name)))
  ) +
  theme_meo +
  theme(legend.position = "bottom")

save_plot(p1, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/comfort_by_gender_period",
          data = means_by_group_period)

# ── 6. Figure 2: Over-time trend of comfort by gender minority ──────────────

# Monthly weighted means
comfort_overtime <- comfort_long %>%
  mutate(survey_month = as.Date(paste0(survey_date, "-01"))) %>%
  group_by(gender_minority, survey_month, item_label) %>%
  summarise(
    wtd_mean = weighted.mean(comfort, wt, na.rm = TRUE),
    n = n(),
    se = sqrt(sum(wt^2 * (comfort - weighted.mean(comfort, wt))^2) / sum(wt)^2),
    .groups = "drop"
  ) %>%
  mutate(
    ci_lo = wtd_mean - 1.96 * se,
    ci_hi = wtd_mean + 1.96 * se
  )

p2 <- ggplot(comfort_overtime,
             aes(x = survey_month, y = wtd_mean, color = gender_minority,
                 fill = gender_minority)) +
  geom_ribbon(aes(ymin = ci_lo, ymax = ci_hi), alpha = 0.15, color = NA) +
  geom_line(linewidth = 0.8) +
  geom_point(size = 1.5) +
  geom_vline(xintercept = as.Date("2025-09-10"), linetype = "dashed", color = "grey40") +
  annotate("text", x = as.Date("2025-09-10"), y = 4.8,
           label = "Kirk assassination\n(Sept 10, 2025)", hjust = -0.05,
           size = 2.8, color = "grey40", family = "poppins") +
  facet_wrap(~item_label, ncol = 1) +
  scale_color_manual(values = c("Cisgender" = "#434E7C", "Trans / Non-binary" = "#FF8200")) +
  scale_fill_manual(values = c("Cisgender" = "#434E7C", "Trans / Non-binary" = "#FF8200")) +
  scale_y_continuous(limits = c(1, 5), breaks = 1:5,
                     labels = c("Not at all", "Not very", "Somewhat", "Comfortable", "Very")) +
  labs(
    title = "Comfort Expressing Political Views Over Time",
    subtitle = "Cisgender vs. Trans / Non-binary respondents",
    x = NULL, y = "Weighted mean comfort (1–5)",
    caption = sprintf("N = %s respondents across %d surveys. Weighted. Shaded area = 95%% CI.",
                      format(nrow(comfort_long %>% distinct(ResponseId)), big.mark = ","),
                      length(unique(comfort_long$survey_name)))
  ) +
  theme_meo +
  theme(legend.position = "bottom")

save_plot(p2, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/comfort_overtime",
          data = comfort_overtime, height = 8)

# ── 7. Figure 3: N trans and non-binary respondents over time ────────────────

nb_trans_counts <- data %>%
  filter(!is.na(gender_group) | !is.na(is_trans)) %>%
  mutate(survey_month = as.Date(paste0(survey_date, "-01"))) %>%
  group_by(survey_name, survey_month) %>%
  summarise(
    n_total = n(),
    n_nonbinary = sum(gender_group == "Non-binary / Other", na.rm = TRUE),
    n_trans = sum(is_trans == "Transgender", na.rm = TRUE),
    n_either = sum(gender_minority == "Trans / Non-binary", na.rm = TRUE),
    pct_nonbinary = n_nonbinary / n_total * 100,
    pct_trans = n_trans / n_total * 100,
    pct_either = n_either / n_total * 100,
    .groups = "drop"
  )

nb_trans_long <- nb_trans_counts %>%
  select(survey_name, survey_month, n_nonbinary, n_trans) %>%
  pivot_longer(cols = c(n_nonbinary, n_trans),
               names_to = "group", values_to = "n") %>%
  mutate(
    group_label = case_when(
      group == "n_nonbinary" ~ "Non-binary / Other gender",
      group == "n_trans" ~ "Transgender"
    )
  )

p3 <- ggplot(nb_trans_long,
             aes(x = survey_month, y = n, color = group_label)) +
  geom_line(linewidth = 0.8) +
  geom_point(size = 2) +
  geom_vline(xintercept = as.Date("2025-09-10"), linetype = "dashed", color = "grey40") +
  annotate("text", x = as.Date("2025-09-10"), y = max(nb_trans_long$n, na.rm = TRUE) * 0.95,
           label = "Kirk assassination", hjust = -0.05,
           size = 2.8, color = "grey40", family = "poppins") +
  scale_color_manual(values = c("Non-binary / Other gender" = "#FF8200",
                                "Transgender" = "#434E7C")) +
  labs(
    title = "Number of Trans and Non-binary Respondents Per Survey",
    subtitle = "MEO tracking surveys, July 2024 – February 2026",
    x = NULL, y = "Number of respondents",
    caption = sprintf("Across %d surveys. Non-binary includes 'I describe myself another way'.\nTransgender from separate self-identification question.",
                      length(unique(nb_trans_long$survey_name)))
  ) +
  theme_meo +
  theme(legend.position = "bottom")

save_plot(p3, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/nb_trans_counts_overtime",
          data = nb_trans_long)

# ── 8. Summary statistics table ──────────────────────────────────────────────

cat("\n\n== N per survey: trans/non-binary ==\n")
nb_trans_counts %>%
  arrange(survey_month) %>%
  select(survey_name, survey_month, n_total, n_nonbinary, n_trans, n_either,
         pct_nonbinary, pct_trans, pct_either) %>%
  print(n = 30)

# ── 9. Kirk-specific comfort items (Oct 2025 survey only) ───────────────────

kirk_data <- data %>%
  filter(survey_name == "2025_10_Tracking", !is.na(gender_minority)) %>%
  select(ResponseId, wt, gender_minority,
         pol_speech_1_r, pol_speech_2_r, pol_speech_3_r,
         chilled_kirk_1_r, chilled_kirk_2_r, chilled_kirk_3_r)

kirk_long <- kirk_data %>%
  pivot_longer(
    cols = c(pol_speech_1_r, pol_speech_2_r, pol_speech_3_r,
             chilled_kirk_1_r, chilled_kirk_2_r, chilled_kirk_3_r),
    names_to = "item",
    values_to = "comfort"
  ) %>%
  filter(!is.na(comfort)) %>%
  mutate(
    context = ifelse(str_detect(item, "kirk"), "About Kirk assassination", "General"),
    item_label = case_when(
      str_detect(item, "1_r") ~ "Express political\nopinions",
      str_detect(item, "2_r") ~ "Respond to posts\nyou disagree with",
      str_detect(item, "3_r") ~ "Express opinions\nat work/school"
    )
  )

kirk_means <- kirk_long %>%
  group_by(gender_minority, context, item_label) %>%
  summarise(
    wtd_mean = weighted.mean(comfort, wt, na.rm = TRUE),
    n = n(),
    se = sqrt(sum(wt^2 * (comfort - weighted.mean(comfort, wt))^2) / sum(wt)^2),
    .groups = "drop"
  ) %>%
  mutate(
    ci_lo = wtd_mean - 1.96 * se,
    ci_hi = wtd_mean + 1.96 * se
  )

cat("\n\n== Kirk-specific vs. General Comfort (Oct 2025) ==\n")
kirk_means %>% arrange(item_label, gender_minority, context) %>% print(n = 20)

p4 <- ggplot(kirk_means,
             aes(x = wtd_mean, y = item_label, color = gender_minority,
                 shape = context)) +
  geom_pointrange(aes(xmin = ci_lo, xmax = ci_hi),
                  position = position_dodge(width = 0.5), size = 0.6) +
  scale_x_continuous(limits = c(1, 5), breaks = 1:5,
                     labels = c("Not at all", "Not very", "Somewhat", "Comfortable", "Very")) +
  scale_color_manual(values = c("Cisgender" = "#434E7C", "Trans / Non-binary" = "#FF8200")) +
  labs(
    title = "Comfort Expressing Political Views: General vs. Kirk-Specific",
    subtitle = "October 2025 tracking survey",
    x = NULL, y = NULL,
    caption = sprintf("N = %s (Oct 2025). Weighted estimates with 95%% CIs.",
                      format(length(unique(kirk_data$ResponseId)), big.mark = ","))
  ) +
  theme_meo +
  theme(legend.position = "bottom")

save_plot(p4, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/kirk_general_comparison",
          data = kirk_means)

cat("\n\nDone! All figures saved to analysis/figures/\n")

## ============================================================================
## Linear models: Trans/NB comfort expressing political views
## ============================================================================

library(dplyr)
library(tidyr)
library(lmtest)
library(sandwich)
library(broom)
library(ggplot2)
library(stringr)

source("C:/Users/math_/.claude/skills/survey-search/scripts/survey_utils.R")
source("C:/Users/math_/Dropbox/PC/Documents/GitHub/ai_interns/templates/meo_theme.R")

# ── 1. Load cleaned/weighted data ───────────────────────────────────────────

catalogue <- load_catalogue()
data <- read.csv("harmonized_data.csv", fileEncoding = "UTF-8-BOM")
cat("Raw rows:", nrow(data), "\n")

data <- clean_survey_data(data, catalogue)
data <- weight_survey_data(data, catalogue, method = "rake")

# ── 2. Recode all variables ─────────────────────────────────────────────────

# Comfort: 0-based (0=Not at all, 4=Very comfortable) → 1-5
recode_comfort_0based <- function(x) {
  x <- as.numeric(x)
  dplyr::case_when(
    x == 0 ~ 1L, x == 1 ~ 2L, x == 2 ~ 3L, x == 3 ~ 4L, x == 4 ~ 5L,
    TRUE ~ NA_integer_
  )
}

data <- data %>%
  mutate(
    # DVs
    comfort_online = recode_comfort_0based(pol_speech_1),
    comfort_respond = recode_comfort_0based(pol_speech_2),
    comfort_work = recode_comfort_0based(pol_speech_3),
    # Gender identity (0=Man, 1=Woman, 2/3=NB/Other, 99=DK)
    gender_identity = coalesce(as.numeric(gender1), as.numeric(gender)),
    gender_group = case_when(
      gender_identity == 0 ~ "Man",
      gender_identity == 1 ~ "Woman",
      gender_identity %in% c(2, 3) ~ "Non-binary / Other",
      TRUE ~ NA_character_
    ),
    is_trans = case_when(
      as.numeric(gender2) == 1 ~ 1L,
      as.numeric(gender2) == 0 ~ 0L,
      TRUE ~ NA_integer_
    ),
    # Combined IV
    gender_minority = case_when(
      gender_group == "Non-binary / Other" | is_trans == 1 ~ 1L,
      gender_group %in% c("Man", "Woman") & (is_trans == 0 | is.na(is_trans)) ~ 0L,
      TRUE ~ NA_integer_
    ),
    # Region FE (user-specified groupings)
    province_num = as.numeric(province),
    region = case_when(
      province_num %in% c(4, 5, 7, 10) ~ "Atlantic",
      province_num == 11 ~ "Quebec",
      province_num == 9 ~ "Ontario",
      province_num == 2 ~ "British Columbia",
      province_num %in% c(1, 3, 12) ~ "Prairies",
      TRUE ~ NA_character_
    ),
    # Controls
    age_num = as.numeric(age),
    pol_interest = as.numeric(pol_intrst_1),
    educ = as.numeric(education),
    inc = coalesce(as.numeric(income), as.numeric(Income)),
  )

# SM use: "uses any platform daily" binary
# Pre-2026 (socialUse_*): 0=Never,...,5=1-2x/day,6=several/day → daily >= 5
# 2026+ (socmed_use_*):   0=Never,1=Monthly,2=Weekly,3=Daily,4=Several/day → daily >= 3
sm_old <- c("socialUse_1", "socialUse_2", "socialUse_3", "socialUse_4",
            "socialUse_5", "socialUse_6", "socialUse_8")
sm_new <- c("socmed_use_1", "socmed_use_2", "socmed_use_3", "socmed_use_4",
            "socmed_use_5", "socmed_use_6", "socmed_use_9")
sm_old <- sm_old[sm_old %in% names(data)]
sm_new <- sm_new[sm_new %in% names(data)]

data <- data %>%
  rowwise() %>%
  mutate(
    # Max across old-scale platforms (daily threshold = 5)
    sm_old_daily = {
      vals <- suppressWarnings(as.numeric(c_across(all_of(sm_old))))
      if (all(is.na(vals))) NA_integer_ else as.integer(max(vals, na.rm = TRUE) >= 5)
    },
    # Max across new-scale platforms (daily threshold = 3)
    sm_new_daily = {
      vals <- suppressWarnings(as.numeric(c_across(all_of(sm_new))))
      if (all(is.na(vals))) NA_integer_ else as.integer(max(vals, na.rm = TRUE) >= 3)
    }
  ) %>%
  ungroup() %>%
  mutate(
    sm_daily = coalesce(sm_old_daily, sm_new_daily),  # 1 = uses any platform daily
    # Period
    end_date = as.Date(EndDate),
    post_kirk = as.integer(end_date >= as.Date("2025-09-10")),
    # Wave as factor
    wave = factor(survey_name)
  )

# Comfort index: mean of the 3 items
data <- data %>%
  rowwise() %>%
  mutate(comfort_index = mean(c(comfort_online, comfort_respond, comfort_work), na.rm = FALSE)) %>%
  ungroup()

# ── 3. Descriptive stats ────────────────────────────────────────────────────

cat("\n== Analysis sample ==\n")
analysis <- data %>%
  filter(!is.na(comfort_index), !is.na(gender_minority), !is.na(age_num),
         !is.na(region))
cat("Full sample (comfort + gender + age + region):", nrow(analysis), "\n")

analysis_full <- analysis %>%
  filter(!is.na(pol_interest), !is.na(sm_daily))
cat("With pol_interest + sm_daily:", nrow(analysis_full), "\n")
cat("\nSM daily use distribution:\n")
analysis_full %>% count(sm_daily) %>% print()

cat("\nGender minority in analysis sample:\n")
analysis_full %>% count(gender_minority) %>% print()

cat("\nRegion distribution:\n")
analysis_full %>% count(region) %>% print()

cat("\nWave distribution:\n")
analysis_full %>% count(wave) %>% arrange(wave) %>% print(n = 30)

# ── 4. Model 1: Wave FE (main model) ────────────────────────────────────────

cat("\n\n========================================\n")
cat("MODEL 1: Wave FE — Comfort index\n")
cat("========================================\n")

m1 <- lm(comfort_index ~ gender_minority + age_num + pol_interest + sm_daily +
            factor(region) + factor(wave),
          data = analysis_full, weights = wt)

# Cluster SEs by wave for robustness
vcov_cl <- vcovCL(m1, cluster = analysis_full$wave)
ct1 <- coeftest(m1, vcov = vcov_cl)

cat("\nCoefficients (clustered SEs by wave):\n")
# Print only substantive coefficients (not wave FE)
coef_names <- rownames(ct1)
substantive <- !grepl("factor\\(wave\\)", coef_names)
print(ct1[substantive, ])

cat("\nR-squared:", summary(m1)$r.squared, "\n")
cat("Adj R-squared:", summary(m1)$adj.r.squared, "\n")
cat("N:", nobs(m1), "\n")

# ── 5. Model 1b-1d: Individual comfort items ────────────────────────────────

for (dv in c("comfort_online", "comfort_respond", "comfort_work")) {
  cat("\n\n--- Model 1 variant:", dv, "---\n")
  f <- as.formula(paste(dv, "~ gender_minority + age_num + pol_interest + sm_daily +
                          factor(region) + factor(wave)"))
  m <- lm(f, data = analysis_full, weights = wt)
  vcov_m <- vcovCL(m, cluster = analysis_full$wave)
  ct <- coeftest(m, vcov = vcov_m)
  substantive_m <- !grepl("factor\\(wave\\)", rownames(ct))
  print(ct[substantive_m, ])
  cat("N:", nobs(m), "\n")
}

# ── 6. Model 2: Post-Kirk interaction (no wave FE, clustered SEs) ───────────

cat("\n\n========================================\n")
cat("MODEL 2: Post-Kirk × Gender Minority interaction\n")
cat("========================================\n")

m2 <- lm(comfort_index ~ gender_minority * post_kirk + age_num + pol_interest +
            sm_daily + factor(region),
          data = analysis_full, weights = wt)

vcov_cl2 <- vcovCL(m2, cluster = analysis_full$wave)
ct2 <- coeftest(m2, vcov = vcov_cl2)
print(ct2)

cat("\nR-squared:", summary(m2)$r.squared, "\n")
cat("N:", nobs(m2), "\n")

# ── 7. Model 2b-2d: Interaction for individual items ────────────────────────

for (dv in c("comfort_online", "comfort_respond", "comfort_work")) {
  cat("\n--- Model 2 variant:", dv, "---\n")
  f <- as.formula(paste(dv, "~ gender_minority * post_kirk + age_num + pol_interest +
                          sm_daily + factor(region)"))
  m <- lm(f, data = analysis_full, weights = wt)
  vcov_m <- vcovCL(m, cluster = analysis_full$wave)
  ct <- coeftest(m, vcov = vcov_m)
  print(ct)
  cat("N:", nobs(m), "\n")
}

# ── 8. Model 3: Without pol_interest and sm_daily (larger N) ──────────────────

cat("\n\n========================================\n")
cat("MODEL 3: Wave FE, no pol_interest/sm_daily (larger sample)\n")
cat("========================================\n")

m3 <- lm(comfort_index ~ gender_minority + age_num + factor(region) + factor(wave),
          data = analysis, weights = wt)

vcov_cl3 <- vcovCL(m3, cluster = analysis$wave)
ct3 <- coeftest(m3, vcov = vcov_cl3)
substantive3 <- !grepl("factor\\(wave\\)", rownames(ct3))
print(ct3[substantive3, ])
cat("N:", nobs(m3), "\n")

# ── 9. Robustness: education and income controls ────────────────────────────

cat("\n\n========================================\n")
cat("MODEL 4: Full controls (+ education + income)\n")
cat("========================================\n")

analysis_r <- analysis_full %>%
  filter(!is.na(educ), !is.na(inc))
cat("N with all controls:", nrow(analysis_r), "\n")

m4 <- lm(comfort_index ~ gender_minority + age_num + pol_interest + sm_daily +
            educ + inc + factor(region) + factor(wave),
          data = analysis_r, weights = wt)

vcov_cl4 <- vcovCL(m4, cluster = analysis_r$wave)
ct4 <- coeftest(m4, vcov = vcov_cl4)
substantive4 <- !grepl("factor\\(wave\\)", rownames(ct4))
print(ct4[substantive4, ])
cat("N:", nobs(m4), "\n")

# ── 10. Coefficient plot ─────────────────────────────────────────────────────

# Collect gender_minority coefficient from all models
extract_coef <- function(model, vcov_cl, label) {
  ct <- coeftest(model, vcov = vcov_cl)
  idx <- which(rownames(ct) == "gender_minority")
  n_obs <- nrow(model$model)
  tibble(
    model = label,
    estimate = ct[idx, 1],
    se = ct[idx, 2],
    ci_lo = ct[idx, 1] - 1.96 * ct[idx, 2],
    ci_hi = ct[idx, 1] + 1.96 * ct[idx, 2],
    p = ct[idx, 4],
    n = n_obs
  )
}

coef_df <- bind_rows(
  extract_coef(m3, vcov_cl3, "Age + Region + Wave FE"),
  extract_coef(m1, vcov_cl, "+ Pol. interest + SM daily"),
  extract_coef(m4, vcov_cl4, "+ Education + Income")
)

coef_df$model <- factor(coef_df$model,
                        levels = rev(c("Age + Region + Wave FE",
                                       "+ Pol. interest + SM daily",
                                       "+ Education + Income")))

p_coef <- ggplot(coef_df, aes(x = estimate, y = model)) +
  geom_vline(xintercept = 0, linetype = "dashed", color = "grey60") +
  geom_pointrange(aes(xmin = ci_lo, xmax = ci_hi), size = 0.6, color = "#FF8200") +
  geom_text(aes(label = sprintf("b = %.2f (N = %s)", estimate, format(n, big.mark = ","))),
            hjust = -0.1, vjust = -0.8, size = 3, family = "poppins") +
  labs(
    title = "Trans / Non-binary Coefficient on Comfort Index (1–5)",
    subtitle = "OLS with survey weights and wave-clustered SEs",
    x = "Coefficient (comfort scale points)", y = NULL,
    caption = "Positive values = more comfortable. All models include wave and region FE."
  ) +
  theme_meo +
  theme(axis.text.y = element_text(size = 9))

save_plot(p_coef, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/coef_plot",
          data = coef_df, width = 7, height = 3.5)

cat("\n\nDone! Models estimated and coefficient plot saved.\n")

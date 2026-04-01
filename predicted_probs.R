## ============================================================================
## Predicted probabilities from ordered logit
## ============================================================================

library(dplyr)
library(tidyr)
library(ggplot2)
library(stringr)
library(MASS)
select <- dplyr::select  # Fix MASS masking

source("C:/Users/math_/.claude/skills/survey-search/scripts/survey_utils.R")
source("C:/Users/math_/Dropbox/PC/Documents/GitHub/ai_interns/templates/meo_theme.R")

# ── 1. Load and recode ──────────────────────────────────────────────────────

catalogue <- load_catalogue()
data <- read.csv("harmonized_data.csv", fileEncoding = "UTF-8-BOM")

data <- clean_survey_data(data, catalogue)
data <- weight_survey_data(data, catalogue, method = "rake")

recode_comfort_0based <- function(x) {
  x <- as.numeric(x)
  dplyr::case_when(
    x == 0 ~ 1L, x == 1 ~ 2L, x == 2 ~ 3L, x == 3 ~ 4L, x == 4 ~ 5L,
    TRUE ~ NA_integer_
  )
}

sm_old <- c("socialUse_1", "socialUse_2", "socialUse_3", "socialUse_4",
            "socialUse_5", "socialUse_6", "socialUse_8")
sm_new <- c("socmed_use_1", "socmed_use_2", "socmed_use_3", "socmed_use_4",
            "socmed_use_5", "socmed_use_6", "socmed_use_9")
sm_old <- sm_old[sm_old %in% names(data)]
sm_new <- sm_new[sm_new %in% names(data)]

data <- data %>%
  mutate(
    comfort_online = recode_comfort_0based(pol_speech_1),
    comfort_respond = recode_comfort_0based(pol_speech_2),
    comfort_work = recode_comfort_0based(pol_speech_3),
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
    gender_minority = case_when(
      gender_group == "Non-binary / Other" | is_trans == 1 ~ 1L,
      gender_group %in% c("Man", "Woman") & (is_trans == 0 | is.na(is_trans)) ~ 0L,
      TRUE ~ NA_integer_
    ),
    province_num = as.numeric(province),
    region = case_when(
      province_num %in% c(4, 5, 7, 10) ~ "Atlantic",
      province_num == 11 ~ "Quebec",
      province_num == 9 ~ "Ontario",
      province_num == 2 ~ "British Columbia",
      province_num %in% c(1, 3, 12) ~ "Prairies",
      TRUE ~ NA_character_
    ),
    age_num = as.numeric(age),
    pol_interest = as.numeric(pol_intrst_1),
    wave = factor(survey_name)
  )

data <- data %>%
  rowwise() %>%
  mutate(
    sm_old_daily = {
      vals <- suppressWarnings(as.numeric(c_across(all_of(sm_old))))
      if (all(is.na(vals))) NA_integer_ else as.integer(max(vals, na.rm = TRUE) >= 5)
    },
    sm_new_daily = {
      vals <- suppressWarnings(as.numeric(c_across(all_of(sm_new))))
      if (all(is.na(vals))) NA_integer_ else as.integer(max(vals, na.rm = TRUE) >= 3)
    }
  ) %>%
  ungroup() %>%
  mutate(sm_daily = coalesce(sm_old_daily, sm_new_daily))

df <- data %>%
  filter(!is.na(comfort_online), !is.na(gender_minority), !is.na(age_num),
         !is.na(region), !is.na(pol_interest), !is.na(sm_daily))

# Ensure factor levels are set before modeling
df$region <- factor(df$region)
df$wave <- factor(df$wave)

cat("Analysis N:", nrow(df), "\n")

# ── 2. Fit ordered logit ────────────────────────────────────────────────────

comfort_labels <- c("Not at all\ncomfortable", "Not very\ncomfortable",
                     "Somewhat\ncomfortable", "Comfortable", "Very\ncomfortable")

fit_ologit <- function(dv_name, df) {
  df$y <- factor(df[[dv_name]], levels = 1:5, ordered = TRUE)
  df <- df %>% filter(!is.na(y))
  polr(y ~ gender_minority + age_num + pol_interest + sm_daily +
         region + wave,
       data = df, weights = wt, Hess = TRUE, method = "logistic")
}

cat("Fitting ordered logits...\n")
m_online  <- fit_ologit("comfort_online", df)
m_respond <- fit_ologit("comfort_respond", df)
m_work    <- fit_ologit("comfort_work", df)
cat("Done.\n")

# ── 3. Predicted probabilities using predict() ─────────────────────────────

get_pred_probs <- function(model, df, dv_label) {
  # Create counterfactual: same data but toggle gender_minority
  df0 <- df; df0$gender_minority <- 0L
  df1 <- df; df1$gender_minority <- 1L

  # Average predicted probabilities (marginal effects approach)
  pred0 <- predict(model, newdata = df0, type = "probs")
  pred1 <- predict(model, newdata = df1, type = "probs")

  # Weighted average across all observations
  w <- df$wt / sum(df$wt)
  avg0 <- colSums(pred0 * w)
  avg1 <- colSums(pred1 * w)

  bind_rows(
    tibble(group = "Cisgender", level = 1:5, level_label = comfort_labels,
           prob = avg0, item = dv_label),
    tibble(group = "Trans / Non-binary", level = 1:5, level_label = comfort_labels,
           prob = avg1, item = dv_label)
  )
}

cat("Computing average predicted probabilities...\n")
pp_all <- bind_rows(
  get_pred_probs(m_online, df, "Express political\nopinions online"),
  get_pred_probs(m_respond, df, "Respond to posts\nyou disagree with"),
  get_pred_probs(m_work, df, "Express opinions\nat work/school")
)

cat("\nPredicted probability distribution:\n")
pp_all %>%
  mutate(prob_pct = round(prob * 100, 1)) %>%
  select(item, group, level_label, prob_pct) %>%
  pivot_wider(names_from = group, values_from = prob_pct) %>%
  print(n = 20)

# ── 4. Bootstrap CIs ────────────────────────────────────────────────────────

cat("\nBootstrapping CIs (200 resamples)...\n")
set.seed(42)
n_boot <- 200

boot_results <- list()
for (b in 1:n_boot) {
  if (b %% 50 == 0) cat("  boot", b, "\n")
  # Resample with replacement within each wave
  boot_df <- df %>%
    group_by(wave) %>%
    slice_sample(prop = 1, replace = TRUE) %>%
    ungroup()

  for (dv in c("comfort_online", "comfort_respond", "comfort_work")) {
    dv_label <- case_when(
      dv == "comfort_online" ~ "Express political\nopinions online",
      dv == "comfort_respond" ~ "Respond to posts\nyou disagree with",
      dv == "comfort_work" ~ "Express opinions\nat work/school"
    )

    boot_df$y <- factor(boot_df[[dv]], levels = 1:5, ordered = TRUE)
    boot_sub <- boot_df %>% filter(!is.na(y))

    m_b <- tryCatch(
      polr(y ~ gender_minority + age_num + pol_interest + sm_daily +
             region + wave,
           data = boot_sub, weights = wt, Hess = FALSE, method = "logistic"),
      error = function(e) NULL
    )
    if (is.null(m_b)) next

    df0 <- boot_sub; df0$gender_minority <- 0L
    df1 <- boot_sub; df1$gender_minority <- 1L
    p0 <- predict(m_b, newdata = df0, type = "probs")
    p1 <- predict(m_b, newdata = df1, type = "probs")
    w <- boot_sub$wt / sum(boot_sub$wt)

    boot_results[[length(boot_results) + 1]] <- tibble(
      boot = b, item = dv_label,
      group = "Cisgender", level = 1:5,
      prob = as.vector(colSums(p0 * w))
    )
    boot_results[[length(boot_results) + 1]] <- tibble(
      boot = b, item = dv_label,
      group = "Trans / Non-binary", level = 1:5,
      prob = as.vector(colSums(p1 * w))
    )
  }
}

boot_df_all <- bind_rows(boot_results)
boot_cis <- boot_df_all %>%
  group_by(group, item, level) %>%
  summarise(
    ci_lo = quantile(prob, 0.025, na.rm = TRUE),
    ci_hi = quantile(prob, 0.975, na.rm = TRUE),
    .groups = "drop"
  )

pp_all <- pp_all %>%
  left_join(boot_cis, by = c("group", "item", "level"))

cat("Done.\n")

# ── 5. Figure: Stacked bar distributions ────────────────────────────────────

pp_all$level_label <- factor(pp_all$level_label, levels = comfort_labels)
pp_all$group <- factor(pp_all$group, levels = c("Cisgender", "Trans / Non-binary"))

comfort_colors <- c(
  "Not at all\ncomfortable" = "#A7D5F2",
  "Not very\ncomfortable"   = "#5FA8D3",
  "Somewhat\ncomfortable"   = "#1D65A6",
  "Comfortable"             = "#0B3C5D",
  "Very\ncomfortable"       = "#072338"
)

p1 <- ggplot(pp_all, aes(x = prob, y = group, fill = level_label)) +
  geom_col(position = "stack", width = 0.7) +
  geom_text(
    aes(label = ifelse(prob > 0.04, sprintf("%.0f%%", prob * 100), ""),
        color = ifelse(level %in% c(1, 2), "dark", "light")),
    position = position_stack(vjust = 0.5),
    size = 2.8, family = "poppins", fontface = "bold", show.legend = FALSE
  ) +
  scale_color_identity() +
  facet_wrap(~item, ncol = 1) +
  scale_fill_manual(values = comfort_colors, guide = guide_legend(reverse = TRUE)) +
  scale_x_continuous(labels = scales::percent_format(), expand = c(0, 0)) +
  labs(
    title = "Predicted Probability of Each Comfort Level",
    subtitle = "Ordered logit with average marginal effects, covariates at observed values",
    x = NULL, y = NULL,
    caption = sprintf("N = %s. Survey-weighted ordered logit with wave and region FE.",
                      format(nrow(df), big.mark = ","))
  ) +
  theme_meo +
  theme(
    legend.position = "bottom",
    panel.grid.major.y = element_blank(),
    strip.text = element_text(size = 9)
  )

save_plot(p1, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/predicted_probs_dist",
          data = pp_all, height = 6)

# ── 6. Figure: Top-2 predicted probabilities ────────────────────────────────

top2 <- pp_all %>%
  filter(level >= 4) %>%
  group_by(group, item) %>%
  summarise(prob_top2 = sum(prob), .groups = "drop")

top2_boot <- boot_df_all %>%
  filter(level >= 4) %>%
  group_by(boot, group, item) %>%
  summarise(prob_top2 = sum(prob), .groups = "drop") %>%
  group_by(group, item) %>%
  summarise(
    ci_lo = quantile(prob_top2, 0.025, na.rm = TRUE),
    ci_hi = quantile(prob_top2, 0.975, na.rm = TRUE),
    .groups = "drop"
  )

top2 <- top2 %>% left_join(top2_boot, by = c("group", "item"))

cat("\nP(Comfortable or Very comfortable):\n")
top2 %>%
  mutate(pct = sprintf("%.1f%% [%.1f, %.1f]", prob_top2 * 100, ci_lo * 100, ci_hi * 100)) %>%
  select(item, group, pct) %>%
  pivot_wider(names_from = group, values_from = pct) %>%
  print()

p2 <- ggplot(top2, aes(x = prob_top2, y = item, color = group)) +
  geom_pointrange(aes(xmin = ci_lo, xmax = ci_hi),
                  position = position_dodge(width = 0.4), size = 0.7) +
  scale_x_continuous(labels = scales::percent_format(), limits = c(0, 0.5)) +
  scale_color_manual(values = c("Cisgender" = "#434E7C", "Trans / Non-binary" = "#FF8200")) +
  labs(
    title = "Predicted P(Comfortable or Very Comfortable)",
    subtitle = "Ordered logit, average marginal effects",
    x = NULL, y = NULL,
    caption = sprintf("N = %s. Cluster-bootstrapped 95%% CIs (200 resamples by wave). Survey-weighted with wave and region FE.",
                      format(nrow(df), big.mark = ","))
  ) +
  theme_meo +
  theme(legend.position = "bottom")

save_plot(p2, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/predicted_probs_top2",
          data = top2)

cat("\nDone! Figures saved.\n")

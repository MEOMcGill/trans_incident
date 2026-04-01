source("C:/Users/math_/.claude/skills/survey-search/scripts/survey_utils.R")
source("C:/Users/math_/Dropbox/PC/Documents/GitHub/ai_interns/templates/meo_theme.R")
library(dplyr)
library(tidyr)
library(lmtest)
library(sandwich)
library(stringr)

# ── 1. Load and prepare data (same as models.R) ──────────────────────────────

catalogue <- load_catalogue()
data <- read.csv("C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/harmonized_data.csv",
                 fileEncoding = "UTF-8-BOM")
data <- clean_survey_data(data, catalogue)
data <- weight_survey_data(data, catalogue, method = "rake")

data <- data %>%
  mutate(
    # Binary DVs (did it at least once in past month)
    dv_post          = as.integer(as.numeric(pol_behav_3) >= 1),
    dv_share         = as.integer(as.numeric(pol_behav_2) >= 1),
    dv_talk_online   = as.integer(as.numeric(pol_talk_3) >= 1),
    dv_talk_coworkers = as.integer(as.numeric(pol_talk_2) >= 1),
    # Gender identity
    gender_identity = as.numeric(gender1),
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
    # Region
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
    educ_num = as.numeric(educ),
    inc = as.numeric(income),
    wave = factor(survey_name)
  )

# SM daily use
sm_old <- c("socialUse_1","socialUse_2","socialUse_3","socialUse_4",
            "socialUse_5","socialUse_6","socialUse_8")
sm_new <- c("socmed_use_1","socmed_use_2","socmed_use_3","socmed_use_4",
            "socmed_use_5","socmed_use_6","socmed_use_9")
sm_old <- sm_old[sm_old %in% names(data)]
sm_new <- sm_new[sm_new %in% names(data)]

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

# Analysis sample
analysis <- data %>%
  filter(!is.na(gender_minority), !is.na(age_num), !is.na(region),
         !is.na(pol_interest), !is.na(sm_daily), !is.na(educ_num))
cat("Analysis N:", nrow(analysis), "\n")
cat("Gender minority:", sum(analysis$gender_minority == 1), "\n")
cat("Cisgender:", sum(analysis$gender_minority == 0), "\n")

# ── 2. Fit models and compute predicted probabilities ─────────────────────────

dv_info <- list(
  list(var = "dv_post",           label = "Posted own political views on SM"),
  list(var = "dv_share",          label = "Shared political news on SM"),
  list(var = "dv_talk_online",    label = "Discussed politics with people online"),
  list(var = "dv_talk_coworkers", label = "Discussed politics with coworkers")
)

results <- list()

for (d in dv_info) {
  dv <- d$var
  label <- d$label

  # Filter to non-missing DV
  df_model <- analysis %>% filter(!is.na(.data[[dv]]))

  # OLS with wave FE, region FE, weighted
  f <- as.formula(paste(dv, "~ gender_minority + age_num + pol_interest + sm_daily +
                         educ_num + factor(region) + factor(wave)"))
  m <- lm(f, data = df_model, weights = wt)
  vcov_cl <- vcovCL(m, cluster = df_model$wave)

  # Predicted probabilities at observed values (average marginal prediction)
  for (gm in c(0, 1)) {
    newdata <- df_model
    newdata$gender_minority <- gm
    preds <- predict(m, newdata = newdata)
    avg_pred <- weighted.mean(preds, df_model$wt)

    # Delta method SE via simulation (1000 draws from coefficient distribution)
    set.seed(42)
    coef_draws <- MASS::mvrnorm(1000, coef(m), vcov_cl)
    X <- model.matrix(f, data = newdata)
    pred_draws <- X %*% t(coef_draws)  # n x 1000
    avg_draws <- apply(pred_draws, 2, function(p) weighted.mean(p, df_model$wt))
    se_pred <- sd(avg_draws)

    results[[length(results) + 1]] <- data.frame(
      dv = label,
      group = ifelse(gm == 1, "Non-binary/Trans", "Cisgender"),
      pct = avg_pred * 100,
      lo = (avg_pred - 1.96 * se_pred) * 100,
      hi = (avg_pred + 1.96 * se_pred) * 100,
      n = nrow(df_model),
      stringsAsFactors = FALSE
    )
  }
}

res <- bind_rows(results)

res$group <- factor(res$group, levels = c("Non-binary/Trans", "Cisgender"))
res$dv <- factor(res$dv, levels = c(
  "Posted own political views on SM",
  "Shared political news on SM",
  "Discussed politics with people online",
  "Discussed politics with coworkers"
))

cat("\nPredicted probabilities:\n")
print(res %>% select(dv, group, pct, lo, hi))

# ── 3. Plot ───────────────────────────────────────────────────────────────────

p <- ggplot(res, aes(x = pct, y = group, color = dv)) +
  geom_pointrange(aes(xmin = lo, xmax = hi),
    size = 0.5, linewidth = 0.7,
    position = position_dodge(width = 0.6)) +
  geom_text(aes(label = paste0(round(pct), "%")),
    vjust = -1.3, size = 3, family = "poppins", show.legend = FALSE,
    position = position_dodge(width = 0.6)) +
  scale_x_continuous(limits = c(0, 80), breaks = seq(0, 80, 20),
                     labels = paste0(seq(0, 80, 20), "%")) +
  scale_color_manual(values = c(
    "Posted own political views on SM" = "#1A4AAD",
    "Shared political news on SM" = "#D71B1E",
    "Discussed politics with people online" = "#229A44",
    "Discussed politics with coworkers" = "#FF8200"
  )) +
  labs(
    title = "Political expression by gender identity",
    subtitle = str_wrap("Predicted % who did each at least once in the past month. OLS controlling for age, political interest, daily SM use, education, region, and survey wave.", width = 80),
    x = NULL, y = NULL,
    caption = paste0("MEO Lab | 17 tracking surveys, Jul 2024 \u2013 Feb 2026 | ",
                     "Cisgender N = ", format(sum(analysis$gender_minority == 0), big.mark = ","),
                     ", Non-binary/Trans N = ", format(sum(analysis$gender_minority == 1), big.mark = ","),
                     "\nAverage predictions at observed covariate values | Wave-clustered SEs via simulation")
  ) +
  theme_meo +
  theme(
    panel.grid.major.y = element_blank(),
    plot.title = element_text(size = 12),
    legend.position = "bottom",
    legend.text = element_text(size = 8)
  ) +
  guides(color = guide_legend(nrow = 2))

save_plot(p, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/figures/political_expression_adjusted",
          width = 7.5, height = 4.5)
cat("\nPlot saved.\n")

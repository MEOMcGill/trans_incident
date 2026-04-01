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

# Comfort: 0-based → 1-5
recode_comfort_0based <- function(x) {
  x <- as.numeric(x)
  dplyr::case_when(
    x == 0 ~ 1L, x == 1 ~ 2L, x == 2 ~ 3L, x == 3 ~ 4L, x == 4 ~ 5L,
    TRUE ~ NA_integer_
  )
}

data <- data %>%
  mutate(
    comfort_online  = recode_comfort_0based(pol_speech_1),
    comfort_respond = recode_comfort_0based(pol_speech_2),
    comfort_work    = recode_comfort_0based(pol_speech_3),
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
    wave = factor(survey_name)
  )

# SM daily use
sm_old <- c("socialUse_1","socialUse_2","socialUse_3","socialUse_4",
            "socialUse_5","socialUse_6","socialUse_8")
sm_old <- sm_old[sm_old %in% names(data)]

data <- data %>%
  rowwise() %>%
  mutate(
    sm_daily = {
      vals <- suppressWarnings(as.numeric(c_across(all_of(sm_old))))
      if (all(is.na(vals))) NA_integer_ else as.integer(max(vals, na.rm = TRUE) >= 5)
    }
  ) %>%
  ungroup()

# Comfort index
data <- data %>%
  rowwise() %>%
  mutate(comfort_index = mean(c(comfort_online, comfort_respond, comfort_work), na.rm = FALSE)) %>%
  ungroup()

# Analysis sample
analysis <- data %>%
  filter(!is.na(comfort_index), !is.na(gender_minority), !is.na(age_num),
         !is.na(region), !is.na(pol_interest), !is.na(sm_daily), !is.na(educ_num))

cat("Analysis N:", nrow(analysis), "\n")
cat("Gender minority:", sum(analysis$gender_minority == 1), "\n")
cat("Cisgender:", sum(analysis$gender_minority == 0), "\n")

# ── 2. Fit model and compute predicted values ─────────────────────────────────

# Three individual DVs + comfort index
dv_info <- list(
  list(var = "comfort_online",  label = "Expressing opinions online"),
  list(var = "comfort_respond", label = "Responding to disagreeable posts"),
  list(var = "comfort_work",    label = "Discussing politics at work/school")
)

results <- list()

for (d in dv_info) {
  dv <- d$var
  label <- d$label

  df_model <- analysis %>% filter(!is.na(.data[[dv]]))

  f <- as.formula(paste(dv, "~ gender_minority + age_num + pol_interest + sm_daily +
                         educ_num + factor(region) + factor(wave)"))
  m <- lm(f, data = df_model, weights = wt)
  vcov_cl <- vcovCL(m, cluster = df_model$wave)

  for (gm in c(0, 1)) {
    newdata <- df_model
    newdata$gender_minority <- gm
    preds <- predict(m, newdata = newdata)
    avg_pred <- weighted.mean(preds, df_model$wt)

    set.seed(42)
    coef_draws <- MASS::mvrnorm(1000, coef(m), vcov_cl)
    X <- model.matrix(f, data = newdata)
    pred_draws <- X %*% t(coef_draws)
    avg_draws <- apply(pred_draws, 2, function(p) weighted.mean(p, df_model$wt))
    se_pred <- sd(avg_draws)

    results[[length(results) + 1]] <- data.frame(
      dv = label,
      group = ifelse(gm == 1, "Non-binary/Trans", "Cisgender"),
      pred = avg_pred,
      lo = avg_pred - 1.96 * se_pred,
      hi = avg_pred + 1.96 * se_pred,
      stringsAsFactors = FALSE
    )
  }
}

res <- bind_rows(results)

res$group <- factor(res$group, levels = c("Non-binary/Trans", "Cisgender"))
res$dv <- factor(res$dv, levels = c(
  "Expressing opinions online",
  "Responding to disagreeable posts",
  "Discussing politics at work/school"
))

cat("\nPredicted comfort (1-5 scale):\n")
print(res %>% select(dv, group, pred, lo, hi) %>% mutate(across(pred:hi, ~round(., 2))))

# ── 3. Plot ───────────────────────────────────────────────────────────────────

p <- ggplot(res, aes(x = pred, y = group, color = dv)) +
  geom_pointrange(aes(xmin = lo, xmax = hi),
    size = 0.5, linewidth = 0.7,
    position = position_dodge(width = 0.6)) +
  geom_text(aes(label = sprintf("%.1f", pred)),
    vjust = -1.3, size = 3, family = "poppins", show.legend = FALSE,
    position = position_dodge(width = 0.6)) +
  scale_x_continuous(limits = c(1, 5), breaks = 1:5,
                     labels = c("1\nNot at all\ncomfortable", "2\nNot very\ncomfortable", "3\nSomewhat\ncomfortable", "4\nComfortable", "5\nVery\ncomfortable"),
                     minor_breaks = NULL) +
  scale_color_manual(values = c(
    "Expressing opinions online" = "#1A4AAD",
    "Responding to disagreeable posts" = "#D71B1E",
    "Discussing politics at work/school" = "#229A44"
  )) +
  labs(
    title = "Comfort with political expression by gender identity",
    subtitle = str_wrap("Predicted values (1\u20135 scale) from OLS controlling for age, political interest, daily SM use, education, region, and survey wave", width = 70),
    x = "Predicted comfort", y = NULL,
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
  guides(color = guide_legend(nrow = 1))

save_plot(p, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/analysis/figures/coef_plot",
          width = 7.5, height = 4)
cat("\nPlot saved.\n")

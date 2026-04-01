source("C:/Users/math_/Dropbox/PC/Documents/GitHub/ai_interns/templates/meo_theme.R")
library(dplyr)
library(tidyr)
library(survey)
library(stringr)

# Load data (weighted file has claims + weights; base file has socialUse columns)
df <- read.csv("C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/harmonized_data_weighted.csv")
df_base <- read.csv("C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/harmonized_data.csv")
su_cols <- grep("^socialUse_", names(df_base), value = TRUE)
df <- df %>% left_join(df_base %>% select(ResponseId, all_of(su_cols)), by = "ResponseId")

# Join survey language (pre-extracted from raw Qualtrics data)
lang_map <- read.csv("C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/lang_map.csv")
df <- df %>% left_join(lang_map, by = "ResponseId")

# Clean: keep finished only, English-speaking respondents only
df <- df %>% filter(Finished == 1, UserLanguage == "EN")

# Weights already in harmonized_data_weighted.csv (wt column)
df$wt <- ifelse(is.na(df$wt), 1, df$wt)

# DV: claims_believe_8 (1=Def false, 2=Prob false, 3=Not sure, 4=Prob true, 5=Def true)
df$believe <- factor(df$claims_believe_8, levels = 1:5,
  labels = c("Definitely false", "Probably false", "Not sure", "Probably true", "Definitely true"))

# Binary: top-2 true
df$believe_true <- as.numeric(df$believe %in% c("Probably true", "Definitely true"))

# Keep only those who rated belief
df <- df %>% filter(!is.na(believe))
cat("N (rated belief):", nrow(df), "\n")

# --- Recode predictors ---

df$age_group <- cut(df$age, breaks = c(0, 29, 44, 59, 100), labels = c("18-29", "30-44", "45-59", "60+"))

df$gender_label <- case_when(
  df$gender1 == 0 ~ "Man",
  df$gender1 == 1 ~ "Woman",
  TRUE ~ NA_character_
)

df$ideo_group <- cut(df$ideology_1, breaks = c(-1, 3, 6, 10),
  labels = c("Left (0-3)", "Centre (4-6)", "Right (7-10)"))

df$party_label <- case_when(
  df$party == 1 ~ "Conservative",
  df$party == 2 ~ "Liberal",
  df$party == 3 ~ "NDP",
  df$party == 4 ~ "Bloc Québécois",
  df$party == 5 ~ "Green",
  df$party == 6 ~ "PPC",
  df$party == 8 ~ "No party",
  TRUE ~ NA_character_
)

# Social media: daily use on ANY platform
# Coding: 0=Never, 1=Once/twice month, 2=Several times month, 3=Once/twice week,
#         4=Several times week, 5=Once/twice day, 6=Several times day
# Daily = codes 5 or 6
su_vars <- paste0("socialUse_", c(1:8))
su_vars <- su_vars[su_vars %in% names(df)]
df$any_daily <- apply(df[su_vars], 1, function(x) any(x >= 5, na.rm = TRUE))
df$daily_label <- case_when(
  df$any_daily == TRUE ~ "Daily SM user",
  df$any_daily == FALSE ~ "Not daily",
  TRUE ~ NA_character_
)

# --- Compute weighted % with CIs ---

compute_ci <- function(data, group_var, facet_label) {
  data <- data %>% filter(!is.na(.data[[group_var]]))
  if (nrow(data) < 10) return(NULL)

  des <- svydesign(ids = ~1, weights = ~wt, data = data)

  results <- data %>%
    distinct(.data[[group_var]]) %>%
    pull(1) %>%
    lapply(function(level) {
      sub <- subset(des, data[[group_var]] == level)
      n_sub <- sum(data[[group_var]] == level, na.rm = TRUE)
      if (n_sub < 10) return(NULL)
      m <- svymean(~believe_true, sub)
      ci <- confint(m)
      data.frame(
        category = as.character(level),
        pct = as.numeric(m) * 100,
        lo = ci[1] * 100,
        hi = ci[2] * 100,
        n = n_sub,
        stringsAsFactors = FALSE
      )
    }) %>% bind_rows()

  results$facet <- facet_label
  results
}

res <- bind_rows(
  compute_ci(df, "age_group", "Age"),
  compute_ci(df, "gender_label", "Gender"),
  compute_ci(df, "ideo_group", "Ideology"),
  compute_ci(df, "daily_label", "Social media")
)

# Order facets
res$facet <- factor(res$facet, levels = c(
  "Age", "Gender", "Ideology", "Social media"
))

# Order categories
cat_order <- c(
  "18-29", "30-44", "45-59", "60+",
  "Man", "Woman",
  "Left (0-3)", "Centre (4-6)", "Right (7-10)",
  "Daily SM user", "Not daily"
)
res$category <- factor(res$category, levels = rev(cat_order))

# Compute overall margin of error for the caption
n_total <- nrow(df)
des_overall <- svydesign(ids = ~1, weights = ~wt, data = df)
m_overall <- svymean(~believe_true, des_overall)
moe_overall <- round(confint(m_overall)[2] * 100 - as.numeric(m_overall) * 100, 1)

# Plot
p <- ggplot(res, aes(x = pct, y = category)) +
  geom_vline(xintercept = 50, linetype = "dashed", color = "grey60", linewidth = 0.3) +
  geom_pointrange(aes(xmin = lo, xmax = hi), size = 0.35, linewidth = 0.5, color = "#1A4AAD") +
  geom_text(aes(label = paste0(round(pct), "%")), vjust = -1.2, size = 2.5, family = "poppins") +
  facet_grid(facet ~ ., scales = "free_y", space = "free_y", switch = "y") +
  scale_x_continuous(limits = c(0, 100), breaks = seq(0, 100, 20),
                     labels = paste0(seq(0, 100, 20), "%")) +
  labs(
    title = '"Schools are indoctrinating kids with\nradical gender ideology"',
    subtitle = "% who believe the claim is probably or definitely true",
    x = NULL, y = NULL,
    caption = str_wrap(paste0("MEO | October 2025 Tracking Survey | English-speaking respondents | N = ", n_total,
                     " (heard of claim) | Weighted estimates with 95% CIs (\u00B1", moe_overall, " pp overall)"), width = 80)
  ) +
  theme_meo +
  theme(
    strip.placement = "outside",
    strip.text.y.left = element_text(angle = 0, hjust = 1, size = 8, face = "bold"),
    panel.grid.major.y = element_blank(),
    panel.spacing = unit(0.4, "lines"),
    plot.title = element_text(size = 11)
  )

save_plot(p, "C:/Users/math_/Dropbox/PC/Documents/GitHub/trans_incident/figures/gender_ideology_belief",
          width = 7, height = 8)
cat("Plot saved.\n")
